"""Hierarchical (H-matrix) compressed operator: accuracy, gates, fallback, planning."""
import os, sys, unittest
from pathlib import Path
from unittest import mock
import numpy as np
from scipy.special import hankel2
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ghost_backend.twod.solver as rcs
from ghost_backend.compressed import hmatrix as H
from ghost_backend.compressed.hmatrix_factor import HMatrixFactor
from test_experimental_cpu import fixture, _circle
from general_fixtures import fixture as general_fixture


class Kernel:
    """Helmholtz single-layer collocation on a closed curve, with an identity term."""
    dropped_routes = 0

    def __init__(self, n=1200, k=60., radius=.5):
        t = 2*np.pi*np.arange(n)/n
        self.xy = np.c_[radius*np.cos(t), .6*radius*np.sin(t)]
        self.h = 2*np.pi*radius/n
        self.k, self.n = k, n
        self.calls = self.entries = 0
        self.dense = self._values(np.arange(n), np.arange(n))

    def _values(self, rows, cols):
        d = np.linalg.norm(self.xy[rows, None] - self.xy[None, cols], axis=2)
        value = np.where(d > 0, .25j*hankel2(0, self.k*np.maximum(d, 1e-300))*self.h, .5)
        return value

    def get_with_error(self, rows, cols):
        rows, cols = np.asarray(rows), np.asarray(cols)
        self.calls += 1; self.entries += len(rows)*len(cols)
        return self.dense[np.ix_(rows, cols)].copy(), np.zeros((len(rows), len(cols)))


def operator(source, **kwargs):
    radius = np.full(source.n, source.h)
    return H.HMatrixOperator(source, source.xy, radius, budget=4*1024**3, **kwargs)


class HierarchicalOperatorTests(unittest.TestCase):
    def test_rebuild_releases_old_storage_and_reprices_inverse(self):
        import weakref
        source = Kernel(900)
        op = operator(source)
        allowance = 4*1024**3
        factor = HMatrixFactor(op, None, storage_budget_bytes=allowance)
        old_blocks = [weakref.ref(row.u) for row in op.near + op.far + op.dense_far]
        old_inverse = weakref.ref(factor.factor)
        max(op.far, key=lambda row: row.u.shape[0]).u *= 1 + 1e-6
        rebuild = op.rebuild
        checked = []
        def retry(tolerance):
            def checkpoint():
                if not checked:
                    self.assertIsNone(old_inverse())
                    self.assertTrue(all(ref() is None for ref in old_blocks))
                    checked.append(True)
            op.checkpoint = checkpoint
            rebuild(tolerance)
        with mock.patch.object(op, 'rebuild', side_effect=retry):
            factor.solve(np.ones((source.n, 1), complex))
        self.assertTrue(checked)
        self.assertEqual(factor.budget, allowance - op.bytes)
        self.assertLessEqual(op.bytes + factor.factor.bytes, allowance)

    def test_operator_products_entries_and_measured_error(self):
        source = Kernel()
        a = source.dense
        op = operator(source)
        self.assertLess(op.evidence['coefficient_fraction'], 1.)
        self.assertLess(op.bytes, 16*a.size)
        rng = np.random.default_rng(3)
        x = rng.standard_normal((source.n, 3)) + 1j*rng.standard_normal((source.n, 3))
        scale = np.max(np.sum(abs(a), axis=1))
        for trans, reference in ((0, a), (1, a.T), (2, a.conj().T)):
            error = np.max(abs(op.matmul(x, trans) - reference @ x))
            self.assertLess(error, 1e-11*scale*np.max(abs(x)))
        rows, cols = rng.choice(source.n, 40, replace=False), rng.choice(source.n, 70, replace=False)
        np.testing.assert_allclose(op.get(rows, cols), a[np.ix_(rows, cols)], atol=1e-11*scale)
        product = op.block_matmul(rows, cols, x[:70])
        np.testing.assert_allclose(product, a[np.ix_(rows, cols)] @ x[:70], atol=1e-11*scale*np.max(abs(x)))
        # The measured (sampled) row error is representative of every row.
        rows = np.arange(source.n)
        true = np.max(np.sum(abs(a - np.vstack([op.get(rows[i:i+64], rows) for i in range(0, source.n, 64)])), axis=1))
        self.assertLessEqual(op.sampled_row_error, H.OPERATOR_ERROR_LIMIT)
        self.assertLess(true/op.operator_norm, 10*max(op.sampled_row_error, 1e-14))
        self.assertGreater(len(op.sample_rows), 0)
        # Exact equilibration agrees with the dense definition.
        expected = rcs._equilibrated_scaling_and_norm_1(a)
        for value, reference in zip(op.equilibrate(), expected):
            np.testing.assert_allclose(value, reference, rtol=1e-9)

    def test_results_do_not_depend_on_thread_count(self):
        source = Kernel(900)
        with mock.patch('ghost_backend.compressed.operator._thread_budget', return_value=1):
            serial = operator(source)
        threaded = operator(source)
        x = np.ones((source.n, 2), complex)
        np.testing.assert_array_equal(serial.matmul(x), threaded.matmul(x))

    def test_factor_solves_and_sampled_gate(self):
        source = Kernel()
        op = operator(source)
        diagnostics = {}
        factor = HMatrixFactor(op, diagnostics, storage_budget_bytes=4*1024**3)
        rng = np.random.default_rng(7)
        b = rng.standard_normal((source.n, 4)) + 1j*rng.standard_normal((source.n, 4))
        x = factor.solve(b)
        np.testing.assert_allclose(x, np.linalg.solve(source.dense, b), rtol=1e-8, atol=1e-10*np.max(abs(x)))
        self.assertLessEqual(factor.event['max_sampled_backward_error'], 1e-12)
        self.assertTrue(np.isfinite(diagnostics['condition_est']))
        reference = np.linalg.cond(source.dense / np.max(abs(source.dense), axis=1)[:, None], 1)
        self.assertLess(abs(np.log10(diagnostics['condition_est']/reference)), 1.)

    def test_inaccurate_operator_is_rejected_then_rebuilt(self):
        source = Kernel()
        with mock.patch.object(H, 'OPERATOR_ERROR_LIMIT', 1e-20):
            with self.assertRaises(H.HMatrixRejected):
                operator(source)
        op = operator(source)
        factor = HMatrixFactor(op, None, storage_budget_bytes=4*1024**3)
        # Corrupt one retained far factor after validation: the exact sample
        # rows catch it, the operator is rebuilt once at a tenth of its
        # tolerance, and the accepted solution meets the gate.
        row = max(op.far, key=lambda r: r.u.shape[0])
        row.u *= 1 + 1e-6
        b = np.ones((source.n, 1), complex)
        x = factor.solve(b)
        self.assertTrue(factor.tightened)
        self.assertIn('sampled_rejection', factor.event)
        self.assertLessEqual(factor.event['max_sampled_backward_error'], 1e-12)
        np.testing.assert_allclose(x, np.linalg.solve(source.dense, b), rtol=1e-8, atol=1e-10*np.max(abs(x)))
        # A second failure is not hidden.
        max(op.far, key=lambda r: r.u.shape[0]).u *= 1 + 1e-6
        with self.assertRaises(H.HMatrixRejected):
            factor.solve(b)

    def test_threshold_and_unsupported_oracles(self):
        with mock.patch.dict(os.environ, {'GHOST_HMATRIX_MIN_UNKNOWNS': '0'}):
            self.assertFalse(H.selected(10**6))
        with mock.patch.dict(os.environ, {'GHOST_HMATRIX_MIN_UNKNOWNS': ''}):
            self.assertFalse(H.selected(H.HMATRIX_MIN_UNKNOWNS - 1))
            self.assertTrue(H.selected(H.HMATRIX_MIN_UNKNOWNS))
        class Thin:
            kind, B, n, mesh = 'thin', .1, 10, None
            def get_with_error(self, rows, cols): raise AssertionError
        self.assertIn('inverse mass', H.unsupported(Thin()))
        class Paired:
            oracles = (Kernel(64), Thin())
        self.assertIsNotNone(H.unsupported(Paired()))

    def test_forecast_bounds_measured_storage(self):
        source = Kernel(1500, k=80.)
        op = operator(source)
        model = H.forecast_storage(source.xy, np.full(source.n, source.h), source.k)
        self.assertGreaterEqual(model['operator_bytes'], .9*op.bytes)
        factor = HMatrixFactor(op, None, storage_budget_bytes=4*1024**3)
        self.assertGreaterEqual(model['inverse_bytes'], .9*factor.factor.bytes)


def _amplitudes(result):
    out = {}
    for sample in result['samples']:
        out.setdefault(sample['polarization'], []).append(complex(sample['rcs_amp_real'], sample['rcs_amp_imag']))
    return {key: np.asarray(value) for key, value in out.items()}


def _thin_gap(count):
    # A 0.5 mm dielectric coat on a PEC core: two surfaces at a thin gap.
    s = dict(segments=[_circle('coat', .0605, count, 3, pos=1), _circle('core', .06, count, 4, pos=1)],
             ibcs=[], dielectrics=[['1', '4', '-.4', '1', '0']])
    return s


class HierarchicalSolveTests(unittest.TestCase):
    """Public 2-D solves: hierarchical compressed backend against dense LU/HODLR."""
    CASES = {
        'pec': (lambda: fixture('pec', 1800), 6.),
        'ibc': (lambda: fixture('ibc', 1800), 6.),
        'dielectric': (lambda: fixture('dielectric', 1100), 6.),
        'lossy_magnetic': (lambda: fixture('magnetic', 900), 3.),
        'coated_ibc_core': (lambda: fixture('coated', 900), 6.),
        'layered': (lambda: fixture('layered', 900), 3.),
        'two_bodies': (lambda: fixture('mixed', 1100), 6.),
        'thin_gap': (lambda: _thin_gap(900), 6.),
        'acute': (lambda: general_fixture('acute', 1800), 6.),
        'reentrant': (lambda: general_fixture('reentrant', 1800), 6.),
    }

    def solve(self, snapshot, frequency, compressed, condition=False):
        environment = {'GHOST_DENSE_BACKEND': 'cpu'}
        if compressed:
            environment.update(GHOST_CPU_FACTORIZATION='compressed', GHOST_HMATRIX_MIN_UNKNOWNS='1000')
        with mock.patch.dict(os.environ, environment):
            return rcs.solve_monostatic_rcs_2d(snapshot, [frequency], [0., 37., 90., 151.],
                                               geometry_units='meters', solver_method='experimental_cpu',
                                               compute_condition_number=condition)

    def check(self, name):
        make, frequency = self.CASES[name]
        dense = self.solve(make(), frequency, False, condition=True)
        compressed = self.solve(make(), frequency, True)
        # Fields agree to 1e-9 of their peak, or to the conditioning-limited
        # change a 1e-12 operator backward error allows (the tile backend
        # differs from dense LU by 1e-9 on the condition-6e3 dielectric).
        allowed = max(1e-9, 2e-12*dense['metadata']['condition_est_max'])
        factors = compressed['metadata']['compressed_factors']
        self.assertTrue(factors)
        for event in factors:
            self.assertEqual(event['compressed'].get('operator'), 'hmatrix', name)
            self.assertLessEqual(event['max_sampled_backward_error'], 1e-12)
            self.assertLessEqual(event['compressed']['sampled_row_error'], H.OPERATOR_ERROR_LIMIT)
        a, b = _amplitudes(dense), _amplitudes(compressed)
        for channel in a:
            difference = np.max(abs(a[channel] - b[channel]))/np.max(abs(a[channel]))
            self.assertLess(difference, allowed, (name, channel, difference))

    def test_pec(self): self.check('pec')
    def test_impedance(self): self.check('ibc')
    def test_dielectric(self): self.check('dielectric')
    def test_lossy_magnetic(self): self.check('lossy_magnetic')
    def test_coated_impedance_core(self): self.check('coated_ibc_core')
    def test_layered(self): self.check('layered')
    def test_two_bodies(self): self.check('two_bodies')
    def test_thin_gap(self): self.check('thin_gap')
    def test_acute(self): self.check('acute')
    def test_reentrant(self): self.check('reentrant')

    def test_tile_operator_below_threshold(self):
        make, frequency = self.CASES['pec']
        with mock.patch.dict(os.environ, {'GHOST_HMATRIX_MIN_UNKNOWNS': '100000'}):
            result = self.solve(make(), frequency, False)
        environment = {'GHOST_DENSE_BACKEND': 'cpu', 'GHOST_CPU_FACTORIZATION': 'compressed',
                       'GHOST_HMATRIX_MIN_UNKNOWNS': '100000'}
        with mock.patch.dict(os.environ, environment):
            tiles = rcs.solve_monostatic_rcs_2d(make(), [frequency], [0., 37., 90., 151.],
                                                geometry_units='meters', solver_method='experimental_cpu')
        for event in tiles['metadata']['compressed_factors']:
            self.assertNotEqual(event['compressed'].get('operator'), 'hmatrix')
        a, b = _amplitudes(result), _amplitudes(tiles)
        for channel in a:
            self.assertLess(np.max(abs(a[channel] - b[channel]))/np.max(abs(a[channel])), 1e-9)

    def test_rejected_operator_falls_back_to_tiles(self):
        make, frequency = self.CASES['pec']
        with mock.patch.object(H, 'OPERATOR_ERROR_LIMIT', 1e-20):
            result = self.solve(make(), frequency, True)
        for event in result['metadata']['compressed_factors']:
            self.assertIn('hmatrix_fallback', event['compressed'])
            self.assertIn('row error', event['compressed']['hmatrix_fallback'])


class HierarchicalLargeSolveTests(unittest.TestCase):
    def test_system_dense_cannot_fit_solves_within_cap(self):
        # 10,000 panels: dense LU/HODLR is forecast above 4 GiB, so a 2.5-GiB
        # solve cap refuses it; the automatic policy solves it with the
        # hierarchical backend and matches the analytic PEC cylinder.
        from ghost_backend.validation.cylinder import sigma_pec_cylinder
        radius, frequency = .5, 6.
        snapshot = dict(segments=[_circle('body', radius, 10000, 2)], ibcs=[], dielectrics=[])
        with mock.patch.dict(os.environ, {'GHOST_MAX_SOLVE_GB': '2.5', 'GHOST_HMATRIX_MIN_UNKNOWNS': '',
                                          'GHOST_CPU_FACTORIZATION': ''}):
            with self.assertRaises(MemoryError):
                with mock.patch.dict(os.environ, {'GHOST_CPU_FACTORIZATION': 'dense'}):
                    rcs.solve_monostatic_rcs_2d(snapshot, [frequency], [0.], geometry_units='meters',
                                                solver_method='experimental_cpu')
            result = rcs.solve_monostatic_rcs_2d(snapshot, [frequency], [0.], geometry_units='meters')
        metadata = result['metadata']
        self.assertEqual(metadata['backend_selection']['selected'], 'compressed')
        events = metadata['compressed_factors']
        self.assertTrue(events and all(e['compressed']['operator'] == 'hmatrix' for e in events))
        self.assertLess(metadata['runtime_profile']['sampled_peak_process_rss_bytes'], 2.5*1024**3)
        for sample in result['samples']:
            pol = {'VV': 'TE', 'HH': 'TM'}[sample['polarization']]
            exact = sigma_pec_cylinder(radius, frequency*1e9, pol)
            self.assertLess(abs(10*np.log10(sample['rcs_linear']/exact)), .01, (pol, sample['rcs_linear'], exact))


class HierarchicalPlanningTests(unittest.TestCase):
    def test_configured_tile_fallback_is_not_forecast_as_hmatrix(self):
        from ghost_backend.compressed.memory import hmatrix_storage
        from ghost_backend.execution.options import execution_scope
        with execution_scope({'compressed_far_method': 'verified_cur'}), \
                mock.patch.object(H, 'forecast_storage', side_effect=AssertionError('wrong forecast')):
            self.assertIsNone(hmatrix_storage(None, [], 'sheet', 20000))
            self.assertIsNotNone(H.unsupported(object()))

    def test_memory_forecast_and_selection_admit_large_system(self):
        # 20,000 panels at 10 GHz: dense needs ~13 GiB, the hierarchical
        # backend about 3 GiB; an 8-GiB budget admits only the latter.
        snapshot = dict(segments=[_circle('body', 4.04, 20000, 2)], ibcs=[], dielectrics=[])
        from ghost_backend.execution.selection import select_backend
        from ghost_backend.execution.options import validate_options, EFFICIENT_DEFAULTS
        options = validate_options(dict(EFFICIENT_DEFAULTS, mesh_strategy='global', ram_budget_gib=8.))
        arguments = dict(geometry_snapshot=snapshot, frequencies_ghz=[10.], elevations_deg=list(range(0, 180, 2)),
                         geometry_units='meters', max_panels=100000)
        with mock.patch.dict(os.environ, {'GHOST_HMATRIX_MIN_UNKNOWNS': ''}):
            selection = select_backend(arguments, options)
        self.assertEqual(selection['selected'], 'compressed')
        self.assertGreater(selection['candidates']['dense']['peak_gb'], 8.)
        self.assertLess(selection['candidates']['compressed']['peak_gb'], 6.)
        record = selection['meshes'][0]
        self.assertEqual(record['resources']['hmatrix_storage']['method'], 'hmatrix_model')


if __name__ == '__main__':
    unittest.main()
