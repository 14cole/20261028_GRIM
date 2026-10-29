"""User choices must survive GUI capture, driver planning, and worker dispatch."""
import importlib
import json
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtWidgets import QApplication

from ghost_backend.execution.options import automatic_options, current_options, validate_options
from ghost_backend.runs.controls import CONTROL_FIELDS, DRIVER_CONTROL_DEFAULTS, run_control_options, run_control_summary
from ghost_backend.runs.execution import driver_execution, driver_options, unit_execution
from ghost_backend.runs.setup import two_d_request
from ghost_backend.ui.app import GhostWorkspace
from ghost_backend.ui.twod_options import TwoDOptionsWidget


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_defaults_alias_and_adaptive_order():
    assert run_control_options() == automatic_options()
    assert run_control_options(dict(factorization='auto'))['factorization'] == 'dense'
    # Existing serialized profiles retain their spelling/fingerprint.
    assert validate_options(dict(factorization='auto'))['factorization'] == 'auto'
    for degree in (1, 2, 3):
        options = run_control_options(dict(basis_order=degree))
        assert options == automatic_options()
        assert 'Automatic' in run_control_summary(options, True)
        assert 'single P1 reference' in run_control_summary(options, False)
        assert 'Survey — mesh convergence not checked' in run_control_summary(options, False)
    with pytest.raises(ValueError):
        run_control_options(dict(basis_order=4))
    with pytest.raises(ValueError):
        run_control_options(dict(factorisation='dense'))


@pytest.mark.parametrize('script,module', [
    ('run_local_monostatic', 'ghost_backend.runs.local_twod_driver'),
    ('run_hpc_monostatic', 'ghost_backend.hpc.twod_driver'),
])
def test_script_controls_capture_and_old_script_defaults(script, module, monkeypatch):
    params = importlib.import_module('ghost_backend.' + script)
    driver = importlib.import_module(module)
    settings = dict(vars(params), FACTORIZATION='compressed', MESH_STRATEGY='local',
                    BASIS_ORDER=3, MESH_GRADING=False, MAX_SOLVE_GB=3)
    # Restore module state after configuration to isolate other driver tests.
    for key in (*driver._PARAMETER_KEYS, '_SCRIPT'):
        monkeypatch.setattr(driver, key, getattr(driver, key, None), raising=False)
    driver.configure(settings, script=params.__file__)
    captured = driver.current_settings()
    expected = dict(factorization='compressed', mesh_strategy='local', basis_order=3, mesh_grading=False)
    profile = driver_options(captured)
    assert all(profile[key] == value for key, value in expected.items())
    assert profile['ram_budget_gib'] == 3
    request = two_d_request([1.], [0., 360.], 'inches', True, 'standard', 'monostatic', [], controls=expected)
    assert all(request['execution_options'][key] == profile[key] for key in expected)
    # Old scripts and repeated configuration must reset, not inherit overrides.
    legacy = {key: value for key, value in settings.items() if key not in CONTROL_FIELDS}
    driver.configure(legacy, script=params.__file__)
    assert all(driver.current_settings()[key] == value for key, value in DRIVER_CONTROL_DEFAULTS.items())


def test_saved_worker_profile_and_pool_context_override_launch_defaults(tmp_path):
    profile = run_control_options(dict(factorization='hierarchical', mesh_strategy='global', basis_order=2,
                                       mesh_grading=False))
    (tmp_path / 'manifest.json').write_text(json.dumps({'solver_config': {
        'solver_method': 'auto', 'lu_precision': 'double', 'execution_options': profile}}))

    @unit_execution
    def unit(unit, context, destination):
        return current_options()

    @driver_execution
    def worker(run_dir_str):
        assert current_options() == profile
        return unit({}, {'execution_options': profile}, None)

    assert worker(str(tmp_path)) == profile
    assert current_options() is None


def test_widget_manual_order_and_legacy_alias(app):
    widget = TwoDOptionsWidget()
    try:
        assert widget.factorization.count() == 4
        assert widget.order.currentText() == 'Automatic'
        assert not widget.order.isEnabled()
        widget.set_value(dict(factorization='auto', mesh_strategy='local', basis_order=3, mesh_grading=False))
        assert widget.factorization.currentData() == 'dense'
        assert widget.order.isEnabled()
        widget.mesh.setCurrentIndex(widget.mesh.findData('adaptive'))
        assert widget.order.currentText() == 'Automatic'
        widget.mesh.setCurrentIndex(widget.mesh.findData('global'))
        assert widget.order.currentData() == 3
        assert widget.value()['mesh_grading'] is False
    finally:
        widget.close()


def test_gui_request_policy_visibility_busy_and_mode_isolation(app):
    workspace = GhostWorkspace()
    try:
        tab = workspace.solver_tab
        controls = dict(factorization='compressed', mesh_strategy='local', basis_order=2, mesh_grading=False)
        tab.twod_options_widget.set_value(controls)
        request = tab._capture_run_setup()
        assert all(request['execution_options'][key] == value for key, value in controls.items())
        assert 'P2' in tab.lbl_run_policy.text()
        assert 'Compressed' in tab.lbl_run_policy.text()
        tab.chk_mesh_certification.setChecked(False)
        assert 'Survey — mesh convergence not checked' in tab.lbl_run_policy.text()
        tab._set_solving_state(True)
        assert not tab.twod_options_widget.isEnabled()
        tab._set_solving_state(False)
        tab.cmb_scatter_mode.setCurrentIndex(tab.cmb_scatter_mode.findData('bistatic'))
        tab.edit_obs_angles.setText('0, 90')
        assert tab.twod_options_widget.isHidden()
        assert tab._capture_run_setup()['execution_options']['factorization'] == 'dense'
        tab.cmb_solver_kind.setCurrentIndex(tab.cmb_solver_kind.findData('bor'))
        assert tab.twod_options_widget.isHidden()
        assert tab.lbl_run_policy.isHidden()
        assert tab._capture_run_setup()['schema'] == 'grim.bor-run-setup'
        tab.cmb_solver_kind.setCurrentIndex(tab.cmb_solver_kind.findData('2d'))
        tab.cmb_scatter_mode.setCurrentIndex(tab.cmb_scatter_mode.findData('monostatic'))
        assert not tab.twod_options_widget.isHidden()
        assert tab._capture_run_setup()['execution_options']['factorization'] == 'compressed'
    finally:
        workspace.close()


@pytest.mark.parametrize('kind,factor,mesh,certified', [
    ('local', 'dense', 'global', True), ('hpc', 'compressed', 'local', False),
])
def test_script_overrides_reach_real_export(tmp_path, kind, factor, mesh, certified):
    from pathlib import Path
    import subprocess
    import sys
    import numpy as np
    from general_fixtures import configured_2d_driver
    from ghost_backend.hpc.common import latest_run_dir, run_status
    backend = Path(__file__).resolve().parents[1]
    geometry = tmp_path / 'geometry'
    geometry.mkdir()
    empty = tmp_path / 'empty'
    empty.mkdir()
    (geometry / 'rectangle.geo').write_text(
        'Title: fixed mesh test\nSegment: rectangle 2\nproperties: 2 40 0 0 0\n'
        '-.02 -.01 -.02 .01\n-.02 .01 .02 .01\n.02 .01 .02 -.01\n.02 -.01 -.02 -.01\n'
        'IBCS_Resistances:\nDielectrics:\n')
    settings = dict(FRD_DIR=str(geometry), OPN_DIR=str(empty), OUTPUT_DIR=str(tmp_path / 'runs'),
                    FREQUENCIES_GHZ=[1.], AZIMUTHS_DEG=[0., 90., 360.], GEOMETRY_UNITS='meters',
                    FACTORIZATION=factor, MESH_STRATEGY=mesh, BASIS_ORDER=2, MESH_GRADING=False,
                    MESH_CERTIFICATION=certified, PLANNING_WORKERS=1)
    settings.update(dict(WORKERS=1) if kind == 'local' else
                    dict(SUBMIT=False, N_NODES=1, N_JOBS=1, MAX_WORKERS_PER_NODE=1))
    script = configured_2d_driver(backend / ('run_' + kind + '_monostatic.py'), tmp_path / 'driver.py', settings)
    env = dict(os.environ, PYTHONPATH=str(backend.parent), OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
               MKL_NUM_THREADS='1', GHOST_TIMING_CACHE_DIR=str(tmp_path / 'timings'))

    def run(arguments):
        result = subprocess.run([sys.executable, str(script), *arguments], cwd=tmp_path, env=env,
                                capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    summary = run([])
    assert 'Run policy' in summary and 'polynomial order: P2' in summary
    if not certified:
        assert 'mesh convergence not checked' in summary
    directory = latest_run_dir(tmp_path / 'runs')
    manifest = json.loads((directory / 'manifest.json').read_text())
    profile = manifest['solver_config']['execution_options']
    assert profile['factorization'] == factor
    assert profile['basis_order'] == 2 and profile['mesh_strategy'] == mesh
    assert profile['mesh_grading'] is False
    if kind == 'hpc':
        env['PYTHONPATH'] = os.pathsep.join((str(directory / 'runtime'), env['PYTHONPATH']))
        env['GHOST_CPU_FACTORIZATION'] = 'invalid-launch-value'
        run(['--worker', str(directory), '0', '0'])
        assert run_status(directory)['attestation_verified']
    results = list((directory / 'results').rglob('*.grim'))
    assert len(results) == 1
    with np.load(results[0], allow_pickle=False) as archive:
        metadata = json.loads(str(archive['solver_metadata_json'].reshape(()).item()))['metadata']
    assert metadata['execution_options'] == profile
    assert metadata['polynomial_degree'] == 2
    assert metadata['mesh_convergence_certified'] is certified
