"""Numerics pins for the 16 October 2026 2-D assembly / linear-algebra speedups.

Each speedup of EFFICIENCY_AUDIT_2026-10-07 adopted here claims bitwise-identical
results (A-2L-3: identical within the solve's backward-error gate); these tests
compare the fast routes with the routines they replace.
"""
from contextlib import nullcontext
from pathlib import Path
import copy
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ghost_backend.twod.solver as rcs
import ghost_backend.twod.operators as ops
import ghost_backend.twod.polynomial_quadrature as pq
from ghost_backend.linalg import workspace
from ghost_backend.twod.assembly.scatter import MatrixDestination, SystemScatter
from ghost_backend.execution.cpu import CPUState, _STATE
from ghost_backend.execution.options import execution_scope, validate_options
from ghost_backend.tests.general_fixtures import fixture


def bitwise(a, b):
    a, b = np.ascontiguousarray(a), np.ascontiguousarray(b)
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


def mesh_for(snapshot, degree, freq=1.):
    from ghost_backend.twod.preparation import prepare_geometry
    with execution_scope(validate_options(dict(basis_order=degree))):
        _, _, materials, scale = prepare_geometry(snapshot, None, 'meters')
        wave, _, _ = rcs._mesh_wavelength_for_snapshot(snapshot, materials, freq)
        panels = rcs._build_panels(snapshot, scale, wave)
        infos = rcs._build_coupled_panel_info(panels, materials, freq, 'TE', 2*np.pi*freq*1e9/rcs.C0)
        return rcs._build_linear_mesh_interface_aware(panels, infos)[0]


def near_pairs(mesh):
    elements = mesh.elements
    pairs = [(elements[i], elements[j]) for i in range(len(elements)) for j in range(len(elements))
             if np.linalg.norm(elements[i].center - elements[j].center)
             < 3 * max(elements[i].length, elements[j].length)]
    # Nearly coincident parallel panels exercise interval bisection.
    close = copy.deepcopy(elements[3])
    for name in ('p0', 'p1', 'center'):
        setattr(close, name, getattr(close, name) + .04 * close.length * close.normal)
    close.panel_index = -1
    return pairs + [(elements[3], close), (close, elements[4])]


def reference_near_blocks(pairs, k, obs_derivative):
    """The former per-task near_blocks loop (classification, projection and test per task)."""
    rtol, max_depth = ops.NEAR_PAIR_QUADRATURE_RTOL, ops.NEAR_PAIR_QUADRATURE_MAX_DEPTH
    table = pq._table_for(k, pairs)

    def moments(tasks, order):
        result, groups = [None] * len(tasks), {}
        for i, task in enumerate(tasks):
            groups.setdefault((task.kind, task.shared), []).append(i)
        for (kind, shared), members in groups.items():
            values = pq._evaluate_chunk([tasks[i] for i in members], pairs, k, obs_derivative, order,
                                        kind, shared, table)
            for i, value in zip(members, values):
                result[i] = value
        return result

    values, parents = {}, {}
    pending = [pq._Task(i, i, 0, ((0., 1.), (0., 1.))) for i in range(len(pairs))]
    next_node = len(pairs)

    def accept(node, value):
        values[node] = value
        while node in parents:
            parent, first, second = parents[node]
            if first not in values or second not in values:
                break
            a, b = values.pop(first), values.pop(second)
            del parents[first], parents[second]
            node = parent
            values[node] = tuple(x + y for x, y in zip(a, b))

    while pending:
        active = pending[-pq._ACTIVE_TASKS:]
        del pending[-len(active):]
        for task in active:
            pq._classify(task, *pairs[task.pair])
        lows, highs = moments(active, 20), moments(active, 36)
        refine, following = [], []
        for task, low_moment, high_moment in zip(active, lows, highs):
            obs, src = pairs[task.pair]
            low, high = pq._project(low_moment, obs, src), pq._project(high_moment, obs, src)
            scale = max(np.max(abs(high[0])), np.max(abs(high[1])), obs.length * src.length * 1e-10)
            error = max(np.max(abs(a - b)) for a, b in zip(low, high))
            if error <= rtol * scale:
                accept(task.node, high)
            elif obs.panel_index == src.panel_index or task.depth >= 2 * max_depth:
                refine.append((task, high, scale))
            else:
                oi, si = task.intervals
                if (oi[1] - oi[0]) * obs.length >= (si[1] - si[0]) * src.length:
                    mid = sum(oi) / 2
                    split = [((oi[0], mid), si), ((mid, oi[1]), si)]
                else:
                    mid = sum(si) / 2
                    split = [(oi, (si[0], mid)), (oi, (mid, si[1]))]
                parents[next_node] = parents[next_node + 1] = (task.node, next_node, next_node + 1)
                following.extend(pq._Task(next_node + j, task.pair, task.depth + 1, interval)
                                 for j, interval in enumerate(split))
                next_node += 2
        if refine:
            unresolved = []
            for (task, high, scale), moment in zip(refine, moments([r[0] for r in refine], 72)):
                finest = pq._project(moment, *pairs[task.pair])
                if max(np.max(abs(a - b)) for a, b in zip(high, finest)) > rtol * scale:
                    unresolved.append((task, finest, scale))
                else:
                    accept(task.node, finest)
            if unresolved:
                for (task, finest, scale), moment in zip(unresolved, moments([u[0] for u in unresolved], 144)):
                    accept(task.node, pq._project(moment, *pairs[task.pair]))
        pending.extend(following)
    return [values[index] for index in range(len(pairs))]


class ThreadedMatrixPassTests(unittest.TestCase):
    """A-2L-1: threaded pre-factor passes equal the serial passes bit for bit."""

    def test_row_norms_and_equilibration_are_thread_independent(self):
        rng = np.random.default_rng(16)
        base = rng.normal(size=(301, 301)) + 1j * rng.normal(size=(301, 301))
        base[:, 7] *= 1e-6
        base[11] *= 1e5
        for order in ('F', 'C'):
            a = np.array(base, order=order)
            serial = workspace.checked_row_norms(a, 4096, workers=1)
            for workers in (2, 5):
                threaded = workspace.checked_row_norms(a, 4096, workers=workers)
                self.assertIsNone(threaded[0])
                self.assertEqual(threaded[1], serial[1])
                self.assertTrue(bitwise(threaded[2], serial[2]))
                bad = a.copy()
                bad[200, 17] = complex(np.nan, 0.)
                bad[31, 250] = complex(1., np.inf)
                self.assertEqual(workspace.checked_row_norms(bad, 4096, workers=workers)[0], (31, 250))
            for row_max in (None, serial[2]):
                expected = rcs._equilibrated_scaling_and_norm_1(a, 64 * 1024, row_max=row_max)
                for workers in (1, 3, 8):
                    actual = workspace.equilibrated_scaling_and_norm_1(a, 64 * 1024, row_max=row_max,
                                                                       workers=workers)
                    self.assertTrue(bitwise(actual[0], expected[0]))
                    self.assertTrue(bitwise(actual[1], expected[1]))
                    self.assertEqual(actual[2], expected[2])

    def test_large_matrices_use_threads(self):
        self.assertEqual(workspace.pass_workers(workspace.PARALLEL_PASS_MIN_BYTES - 1), 1)
        self.assertEqual(workspace.pass_workers(10, workers=3), 3)

    def test_dense_factor_scaling_matches_the_solver_routine(self):
        from ghost_backend.linalg.dense import DenseFactor
        rng = np.random.default_rng(5)
        a = np.asfortranarray(rng.normal(size=(160, 160)) + 1j * rng.normal(size=(160, 160)) + 30 * np.eye(160))
        with mock.patch.object(workspace, 'PARALLEL_PASS_MIN_BYTES', 0):
            factor = DenseFactor(a, {})
        expected = rcs._equilibrated_scaling_and_norm_1(a)
        for x, y in zip(factor._condition_scaling[:2], expected[:2]):
            self.assertTrue(bitwise(x, y))
        self.assertEqual(factor._condition_scaling[2], expected[2])
        self.assertEqual(factor.matrix_inf, workspace.matrix_inf_norm(a))


class BatchedPolynomialNearTests(unittest.TestCase):
    """A-2D-3 / A-2D-8: batched classification, keys, projection and test of near_blocks."""

    @classmethod
    def setUpClass(cls):
        cls.meshes = {degree: mesh_for(fixture('rectangle', 16), degree) for degree in (2, 3)}

    def test_near_blocks_equal_the_per_task_rule(self):
        # Thin-gap pairs (the 0.04 L parallel pair) take the semi-analytic
        # moments instead; they agree with the per-task rule to its target.
        for degree, mesh in self.meshes.items():
            pairs = near_pairs(mesh)
            thin = np.flatnonzero(pq._thin_gap_mask(pq._PairGeometry(pairs), pairs))
            self.assertEqual(len(thin), 2)
            for k in (37.5, 51 - 7j, 420.8 - 204.6j):
                for derivative in (True, False):
                    actual = pq.near_blocks(pairs, k, derivative, threads=2)
                    expected = reference_near_blocks(pairs, k, derivative)
                    thin_values = dict(zip(thin, pq._thin_gap_values(pq._PairGeometry(pairs), pairs, thin,
                                                                     k, derivative)))
                    for index, (got, want) in enumerate(zip(actual, expected)):
                        for x, y, z in zip(got, want, thin_values.get(index, want)):
                            self.assertTrue(bitwise(np.asarray(x), np.asarray(z)), (degree, k, derivative))
                            if index in thin_values:
                                scale = max(np.max(np.abs(c)) for c in want)
                                self.assertLess(np.max(np.abs(x - y)), 1e-8 * scale, (degree, k, derivative))

    def test_classification_and_keys_equal_the_per_task_routines(self):
        mesh = self.meshes[3]
        pairs = near_pairs(mesh)
        # Welded ends at the snap tolerance and sub-interval tasks.
        obs = SimpleNamespace(p0=np.array([0., 0.]), p1=np.array([.01, 0.]), node_ids=(0, 1, 2, 3),
                              panel_index=100, normal=np.array([0., 1.]), length=.01)
        welded = SimpleNamespace(p0=np.array([.0100000015, 0.]), p1=np.array([.02, 0.]), node_ids=(1, 4, 5, 6),
                                 panel_index=101, normal=np.array([0., 1.]), length=.0099999985)
        pairs = pairs + [(obs, welded), (welded, obs), (obs, obs)]
        intervals = [((0., 1.), (0., 1.)), ((0., .5), (0., 1.)), ((.5, 1.), (0., .25)), ((.25, .5), (.25, .5))]
        tasks = [pq._Task(0, p, 0, iv) for p in range(len(pairs)) for iv in intervals]
        geometry = pq._PairGeometry(pairs)
        batch = pq._TaskBatch.build(tasks, pairs, geometry, 51 - 7j, True)
        for task, code, row in zip(tasks, batch.codes, batch.key_rows):
            pq._classify(task, *pairs[task.pair])
            self.assertEqual(pq._KINDS[int(code)], (task.kind, task.shared))
            row = row.copy()
            row[8] = 36.
            self.assertEqual(row.tobytes(), pq._moment_key(51 - 7j, True, *pairs[task.pair], task, 36))
        self.assertTrue(np.any(batch.codes >= 2) and np.any(batch.codes == 1) and np.any(batch.codes == 0))

    def test_box_moments_from_arrays_equal_the_element_route(self):
        mesh = self.meshes[3]
        elements = mesh.elements
        obs_ids = np.arange(len(elements))
        src_ids = (obs_ids + 3) % len(elements)
        geometry = (np.asarray([e.p0 for e in elements], float), np.asarray([e.p1 for e in elements], float),
                    np.asarray([e.p1 - e.p0 for e in elements], float), np.asarray([e.length for e in elements]),
                    np.asarray([e.normal for e in elements], float))
        for k in (37.5, 51 - 7j):
            for derivative in (True, False):
                for cached in (False, True):
                    with (pq.moment_cache_scope() if cached else nullcontext()):
                        plain = ops._box_blocks_polynomial(elements, obs_ids, src_ids, k, derivative, 9, True, True)
                    with (pq.moment_cache_scope() if cached else nullcontext()):
                        arrays = ops._box_blocks_polynomial(elements, obs_ids, src_ids, k, derivative, 9, True, True,
                                                            prepared_geometry=geometry)
                    for x, y in zip(plain, arrays):
                        self.assertTrue(bitwise(x, y))
        obs, src = [elements[i] for i in obs_ids], [elements[i] for i in src_ids]
        self.assertEqual(pq.box_moment_keys(51 - 7j, True, 9, True, False, obs, src),
                         pq.box_moment_key_rows(51 - 7j, True, 9, True, False, geometry[0][obs_ids],
                                                geometry[1][obs_ids], geometry[4][obs_ids], geometry[0][src_ids],
                                                geometry[1][src_ids], geometry[4][src_ids]))


class LinearNearBatchTests(unittest.TestCase):
    """A-2D-8 / A-2D-9: array-fed touching batches and the vectorized self series."""

    def test_self_series_equals_the_scalar_routine(self):
        rng = np.random.default_rng(9)
        for k in (1.0, 62.8, 62.8 - 5j, 400 - 300j, 1e-3, 5 - 60j):
            lengths = np.concatenate([rng.uniform(1e-6, 1., 400) * rng.choice([1e-3, 1e-2, .1, 1., 10.], 400),
                                      [0., 8. / abs(k), 7.999 / abs(k), 1e-40]])
            for length, block in zip(lengths, ops._single_layer_self_blocks_exact_many(lengths, k)):
                reference = ops._single_layer_self_block_exact(SimpleNamespace(length=length), k)
                self.assertEqual(reference is None, block is None)
                if reference is not None:
                    self.assertTrue(bitwise(block, reference), (k, length))

    def test_touching_batches_from_arrays_equal_the_pair_route(self):
        mesh = mesh_for(fixture('reentrant', 48), 1)
        elements = mesh.elements
        n = len(elements)
        obs_ids, src_ids = np.arange(n), (np.arange(n) + 1) % n
        p0 = np.asarray([e.p0 for e in elements], float)
        p1 = np.asarray([e.p1 for e in elements], float)
        geometry = (p0, p1, p1 - p0, np.asarray([e.length for e in elements]),
                    np.asarray([e.normal for e in elements], float))
        node_ids = np.asarray([e.node_ids for e in elements])
        touching, obs_start, src_start = ops._shared_endpoints(p0, p1, node_ids, obs_ids, src_ids)
        self.assertTrue(touching.all())
        shared = np.column_stack((obs_start, src_start))
        pairs = [(elements[i], elements[j]) for i, j in zip(obs_ids, src_ids)]
        for k in (40., 40. - 9j):
            for derivative in (True, False):
                expected = ops._integrate_linear_touching_pairs_sk_batched(pairs, shared, k, derivative, 9)
                actual = ops._integrate_linear_touching_pairs_sk_batched(
                    None, shared, k, derivative, 9,
                    geometry=ops._touching_geometry_arrays(geometry, obs_ids, src_ids, derivative))
                for x, y in zip(expected, actual):
                    self.assertTrue(bitwise(x, y))


def fused(mesh, k, mask=None):
    n = len(mesh.nodes)
    ids = np.arange(n)
    mats = [np.zeros((n, n), complex, order='F') for _ in range(4)]
    ops._assemble_linear_operator_matrices_multi(mesh, k, True, [mask],
        output_node_ids_many=[(ids, ids)], double_layer_output_node_ids_many=[(ids, ids)],
        operator_outputs=[(MatrixDestination(mats[0], n), MatrixDestination(mats[1], n))],
        additional_operator_outputs=[(MatrixDestination(mats[2], n), MatrixDestination(mats[3], n))])
    return mats


class ConcurrentFarCommitTests(unittest.TestCase):
    """A-2D-4: far tiles committed concurrently in conflict order give the serial sums."""

    def test_fused_operators_are_bitwise_the_ordered_commit(self):
        for degree in (1, 3):
            mesh = mesh_for(fixture('reentrant', 160), degree, 3.)
            results = []
            for concurrent in (False, True):
                with mock.patch.object(ops, 'CONCURRENT_FAR_COMMITS', concurrent), \
                        execution_scope(validate_options(dict(assembly_threads=4, assembly_tile=12))), \
                        _STATE.override(CPUState()):
                    results.append(fused(mesh, 40.0 - 1j))
            for a, b in zip(*results):
                self.assertTrue(bitwise(a, b))

    def test_regional_solves_are_bitwise_the_ordered_commit(self):
        calls = []
        real = ops._run_dependent_tiles

        def counted(*args, **kwargs):
            calls.append(1)
            return real(*args, **kwargs)
        for case, options in (('mixed', {}), ('dielectric', dict(basis_order=2)), ('sheet', {})):
            amplitudes = []
            for concurrent in (False, True):
                calls.clear()
                with mock.patch.object(ops, 'CONCURRENT_FAR_COMMITS', concurrent), \
                        mock.patch.object(ops, '_run_dependent_tiles', counted):
                    result = rcs.solve_monostatic_rcs_2d(fixture(case, 160), [3.], [0., 41., 90.],
                        geometry_units='meters',
                        execution_options=dict(assembly_threads=4, assembly_tile=16, **options))
                self.assertEqual(bool(calls), concurrent, case)
                amplitudes.append(np.array([complex(r['rcs_amp_real'], r['rcs_amp_imag'])
                                            for rows in result['co_solved_samples'].values() for r in rows]))
            self.assertTrue(bitwise(*amplitudes), case)

    def test_overlapping_or_custom_targets_keep_the_ordered_commit(self):
        n = 6
        matrix = np.zeros((2 * n, 2 * n), complex, order='F')
        ids = np.arange(n)
        top, bottom = matrix[:n, :n], matrix[n:, :n]
        self.assertTrue(ops.independent_commit_targets([MatrixDestination(top, n), MatrixDestination(bottom, n)]))
        self.assertFalse(ops.independent_commit_targets([MatrixDestination(matrix[:n, :n], n),
                                                         MatrixDestination(matrix[1:n + 1, :n], n)]))
        # Two nodes routed into one destination row.
        row_map = np.full(n, -1)
        row_map[[0, 1]] = 0
        merged = SystemScatter(matrix, n, ids, ids, [(row_map, ids, None)])
        self.assertFalse(ops.independent_commit_targets([merged]))

        class Custom(SystemScatter):
            def scatter_add(self, rows, columns, values):
                pass
        self.assertFalse(ops.independent_commit_targets([Custom(matrix, n, ids, ids, [(ids, ids, None)])]))

    def test_conflicts_cover_every_shared_node_rectangle(self):
        mesh = mesh_for(fixture('rectangle', 40), 1)
        node_ids = np.asarray([e.node_ids for e in mesh.elements])
        sel = np.arange(len(mesh.elements))
        tile = 7
        tiles = [(i0, j0) for i0 in range(0, len(sel), tile) for j0 in range(i0, len(sel), tile)]
        conflicts = ops.FarTileConflicts(tiles, tile, sel, sel, node_ids, True, len(mesh.nodes))

        def rectangles(index):
            i0, j0 = tiles[index]
            rows, cols = set(node_ids[i0:i0 + tile].ravel()), set(node_ids[j0:j0 + tile].ravel())
            return [(rows, cols)] + ([(cols, rows)] if j0 > i0 else [])
        for t in range(len(tiles)):
            found = set(conflicts.conflicting(t, list(range(t))).tolist())
            for u in range(t):
                meets = any(r & r2 and c & c2 for r, c in rectangles(t) for r2, c2 in rectangles(u))
                self.assertEqual(u in found, meets, (t, u))


class LuDirectRuleTests(unittest.TestCase):
    """A-2L-3: dense 2-D LU factors solve wide 'auto' batches directly from 512 unknowns."""

    def test_dense_factor_solves_directly_and_other_factors_keep_the_threshold(self):
        from ghost_backend.linalg import sweep
        from ghost_backend.linalg.dense import DenseFactor
        rng = np.random.default_rng(3)
        n = 1200
        a = np.asfortranarray(rng.normal(size=(n, n)) + 1j * rng.normal(size=(n, n)) + 60 * np.eye(n))
        x = np.linspace(-1, 1, n)[:, None]
        rhs = np.exp(1j * 20 * x * np.cos(np.linspace(0, np.pi, 181))[None, :])
        factor = DenseFactor(a)
        solved = sweep.solve(factor, rhs, sweep.SweepBasis(181), setting='auto')
        self.assertEqual(factor.event['sweep_compression'].get('lu_direct_batches'), 1)
        self.assertTrue(bitwise(solved, DenseFactor(a).solve(rhs)))
        self.assertEqual(sweep._lu_direct_min_unknowns(factor), 512)
        self.assertEqual(sweep._lu_direct_min_unknowns(SimpleNamespace(lu=1)), sweep.LU_DIRECT_MIN_UNKNOWNS)
        self.assertFalse(sweep._lu_direct(SimpleNamespace(lu=1, hierarchical=None, mixed=None), n, 181))
        # Narrow batches keep the QR attempt.
        narrow = DenseFactor(a)
        sweep.solve(narrow, rhs[:, :96], sweep.SweepBasis(96), setting='auto')
        self.assertNotIn('lu_direct_batches', narrow.event['sweep_compression'])
        # The QR route, still taken by factors without the opt-in, agrees within the gate.
        with mock.patch.object(DenseFactor, 'lu_direct_min_unknowns', sweep.LU_DIRECT_MIN_UNKNOWNS):
            other = DenseFactor(a)
            compressed = sweep.solve(other, rhs, sweep.SweepBasis(181), setting='auto')
        self.assertNotIn('lu_direct_batches', other.event['sweep_compression'])
        self.assertLess(np.max(np.abs(compressed - solved)) / np.max(np.abs(solved)), 1e-12)


class KernelTableBuildTests(unittest.TestCase):
    """A-2D-10: the shared Chebyshev-to-power matrix is the one each table formed."""

    def test_shared_conversion_matrix(self):
        from numpy.polynomial import Chebyshev, Polynomial
        from ghost_backend.twod.assembly.kernels import _chebyshev_to_power
        n = 13
        expected = np.zeros((n, n))
        for j in range(n):
            co = Chebyshev.basis(j, domain=[0, 1]).convert(kind=Polynomial).coef
            expected[:len(co), j] = co
        self.assertTrue(bitwise(_chebyshev_to_power(n), expected))
        self.assertFalse(_chebyshev_to_power(n).flags.writeable)


if __name__ == '__main__':
    unittest.main()
