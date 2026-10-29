from dataclasses import replace
from unittest import mock
import copy
import math
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from ibc.compute import LayerConfig, ConstantMaterial, LoadedLayer, UncertaintyConfig, InverseCandidate, C0, ETA0
from ibc.design_search import InverseSearchRequest, run_inverse_search, score_inverse_candidate
from ibc.inverse_grid import DesignGrid
from ibc.inverse_workflow import search_identity
from ibc.robust_design import (manufacturing_scenarios, score_manufacturing, load_design, verify_candidates,
                              validate_robust_setup, bound_scenarios, candidate_configs, manufacturing_case_count)
from ibc.tolerance_analysis import StopToleranceAnalysis, run_tolerance_study, repeatability
from ibc.tolerance_config import DEFAULT_SPEC, SETUP_DEFAULTS
from ibc.ui_options import INVERSE_SCORE_WHOLE_BAND, INVERSE_SCORE_ROBUST, INVERSE_SCORE_YIELD

CFG = UncertaintyConfig(False, 0, 0, 0)
SETUP = dict(samples=16, seed=81, repeats=2, levels=1)

def screen():
    return [LayerConfig(0, False, '', '', 0, is_sheet=True, sheet_resistance=ETA0,
                        inv_rs_min=250, inv_rs_max=450, inv_rs_accuracy=100,
                        tolerances={'sheet_resistance': dict(DEFAULT_SPEC, bound=50)}),
            LayerConfig(C0/10e9/4/.0254, False, '', '', 0, material_source='constant')]

def candidate(configs):
    return InverseCandidate(0,0,0,0,0,[0 if c.is_sheet else c.thickness_in for c in configs],
                            ['']*len(configs), [c.sheet_resistance if c.is_sheet else 0 for c in configs])

def statistics(v): return np.mean(v),np.min(v),np.max(v)
def scorer(*a,**kw): return score_inverse_candidate(*a,**kw, stop_requested=lambda:False,statistics=statistics)
def request(configs, mode=INVERSE_SCORE_ROBUST, pol='both'):
    return InverseSearchRequest(configs,[10.],[0.],pol,CFG,mode,None,DesignGrid(configs),3,'10 GHz',0,0,True,-20,SETUP)

@pytest.mark.parametrize('mode',[INVERSE_SCORE_ROBUST, INVERSE_SCORE_YIELD])
def test_manufacturing_ranking_matches_analytic_quarter_wave(mode):
    configs = screen()
    req = request(configs,mode)
    result, state = run_inverse_search(req,stop_requested=lambda:False,progress=lambda *a:None,score_candidate=scorer)
    params, cases = manufacturing_scenarios(configs,SETUP,mode)
    expected = []
    for r in [250,350,450]:
        resistance = r*(1+.5*cases[:,0])
        db = 20*np.log10(np.abs((resistance-ETA0)/(resistance+ETA0)))
        nominal = 20*math.log10(abs((r-ETA0)/(r+ETA0)))
        score = 100*np.mean(db > -20) if mode==INVERSE_SCORE_YIELD else max(nominal,float(db.max()))+20
        expected.append(score)
    np.testing.assert_allclose(np.asarray(state['score_rows'])[::5],expected,atol=1e-10)
    assert [c.sheet_resistance_ohm[0] for c in result[0]] == [[250,350,450][i] for i in sorted(range(3),key=lambda i:(expected[i],i))]
    assert len(result[3][0][0]) == manufacturing_case_count(configs,SETUP,mode)

def test_both_polarizations_use_joint_worst_point_and_conservative_plot():
    configs=screen();configs[0].tolerances={}
    req=replace(request(configs,INVERSE_SCORE_WHOLE_BAND),target_freqs=[8.,10.],target_angles=[0.,65.],a_stop=65)
    all_results={}
    for pol in ['te','tm','both']:
        all_results[pol]=run_inverse_search(replace(req,wave_pol=pol),stop_requested=lambda:False,progress=lambda *a:None,score_candidate=scorer)
    te=np.asarray(all_results['te'][1]['score_rows']).reshape(-1,5)
    tm=np.asarray(all_results['tm'][1]['score_rows']).reshape(-1,5)
    both=np.asarray(all_results['both'][1]['score_rows']).reshape(-1,5)
    np.testing.assert_allclose(both[:,0],np.maximum(te[:,0],tm[:,0]))
    # Verify each plotted candidate uses the worst polarization at each angle.
    for cand, plotted in zip(all_results['both'][0][0],all_results['both'][0][3]):
        from ibc.compute import compute_angle_metrics_many
        layers=load_design(candidate_configs(configs,cand))
        expected=np.asarray([np.maximum(*[compute_angle_metrics_many([8.,10.],a,layers,p)['metal_loss_db'] for p in ['te','tm']]) for a in [0.,65.]]).T
        np.testing.assert_allclose(plotted,expected)

@pytest.mark.parametrize('mode',[INVERSE_SCORE_ROBUST, INVERSE_SCORE_YIELD])
def test_shared_scenarios_resume_and_identity(mode):
    req=request(screen(),mode)
    completed=[0]
    first,state=run_inverse_search(req,stop_requested=lambda:completed[0]>=1,
        progress=lambda d,*a:completed.__setitem__(0,d),score_candidate=scorer)
    assert state['next_index']==1
    resumed, rs=run_inverse_search(replace(req,checkpoint=copy.deepcopy(state)),stop_requested=lambda:False,progress=lambda *a:None,score_candidate=scorer)
    full, fs=run_inverse_search(req,stop_requested=lambda:False,progress=lambda *a:None,score_candidate=scorer)
    assert rs['score_rows']==fs['score_rows'] and resumed[0]==full[0]
    changed=copy.deepcopy(req.layer_snapshot);changed[0].tolerances['sheet_resistance']['bound']=40
    for altered in [replace(req,layer_snapshot=changed),replace(req,robust_setup=dict(SETUP,seed=82)),replace(req,robust_setup=dict(SETUP,samples=32))]:
        with pytest.raises(ValueError,match='changed'):
            run_inverse_search(replace(altered,checkpoint=copy.deepcopy(state)),stop_requested=lambda:False,progress=lambda *a:None,score_candidate=scorer)

def test_verification_catches_between_frequency_failure_and_preserves_discrete_scope():
    configs=screen();configs[0].tolerances={};configs[1].thickness_in=C0/2e9/4/.0254
    cand=candidate(configs)
    band=verify_candidates(configs,[cand],[2.,6.,10.],[0.],'both',CFG,-10,SETUP)
    result=band['candidates'][0]
    assert result['refinement_history'][0]['margin_db']>200
    assert result['worst_margin_db']==pytest.approx(-10,abs=1e-10)
    assert result['worst_condition']['frequency_ghz'] in [4.,8.]
    discrete=verify_candidates(configs,[cand],[2.,6.,10.],[0.],'te',CFG,-10,SETUP,continuous=False)
    assert discrete['candidates'][0]['worst_margin_db']>200
    assert discrete['frequency_scope']=='discrete targets only'

def test_joint_interior_verification_detects_thickness_alias_and_increases_samples():
    configs=screen();configs[0].tolerances={};configs[1].thickness_in=17*C0/10e9/4/.0254
    cfg=UncertaintyConfig(True,1600/17,0,0)
    result=verify_candidates(configs,[candidate(configs)],[10.],[0.],'te',cfg,-10,dict(SETUP,levels=2))
    row=result['candidates'][0]
    assert row['worst_margin_db'] < -9
    assert row['refinement_history'][-1]['cases'] > row['refinement_history'][0]['cases']

def test_independent_yield_repeats_and_seed_separation():
    configs=screen()
    result=verify_candidates(configs,[candidate(configs)],[10.],[0.],'te',CFG,-20,dict(SETUP,samples=1024,repeats=4))
    estimate=result['candidates'][0]['yield_estimate']
    assert SETUP['seed'] not in result['yield_seeds']
    assert len(set(result['yield_seeds']))==4
    assert abs(estimate['mean_pass_pct']-40.4040404)<.2
    assert estimate['standard_error_percentage_points']>=0
    summary=repeatability([40,50,60,50])
    assert summary['mean_pass_pct']==50
    assert summary['standard_error_percentage_points']==pytest.approx(np.std([40,50,60,50],ddof=1)/2)

def test_standalone_yield_repeats_are_captured_and_counted():
    configs=screen()
    setup=dict(SETUP_DEFAULTS,f_start='10',f_stop='10',a_start='0',a_stop='0',
               target='-20',samples='64',repeats='3',points='5',mode='Sensitivity + statistical trials')
    result=run_tolerance_study(load_design(configs),configs,setup)
    assert result['trials']==192 and len(result['repeatability']['repeat_pass_pct'])==3
    assert result['evaluated']==197 and result['workload']['evaluations']==197
    assert result['pass_fraction_pct']==pytest.approx(result['repeatability']['mean_pass_pct'])

def test_verification_validation_cancellation_and_no_double_counting():
    configs=screen();cand=candidate(configs)
    with pytest.raises(StopToleranceAnalysis):
        verify_candidates(configs,[cand],[10.],[0.],'both',CFG,-20,SETUP,stop_requested=lambda:True)
    with pytest.raises(ValueError,match='double-counting'):
        verify_candidates(configs,[cand],[10.],[0.],'both',UncertaintyConfig(True,5,5,5),-20,SETUP)
    for invalid in [dict(samples=17),dict(levels=0),dict(repeats=1),dict(seed=-1),dict(samples=16.5)]:
        with pytest.raises(ValueError): validate_robust_setup(invalid)
    with pytest.raises(ValueError,match='strictly increasing'):
        verify_candidates(configs,[cand],[10.,9.],[0.],'te',CFG,-20,SETUP)
    with mock.patch('ibc.robust_design.load_design',side_effect=AssertionError('must reject before loading')):
        with pytest.raises(ValueError):
            verify_candidates(configs,[cand],list(np.linspace(1,100,10000)),list(np.linspace(0,89,1000)),'both',CFG,-20,dict(SETUP,levels=4))

@pytest.fixture
def gui():
    from ibc.ui import ImpedanceGui
    app=QApplication.instance() or QApplication([])
    ui=ImpedanceGui()
    yield ui
    ui.deleteLater();app.processEvents()

def test_ui_default_project_roundtrip_and_verification(gui):
    assert gui.inv_score_mode_var.get()==INVERSE_SCORE_WHOLE_BAND
    gui.layers=screen()
    gui.inv_score_mode_var.set(INVERSE_SCORE_YIELD)
    gui.inv_wave_pol_var.set('Both')
    gui.inv_uncertainty_var.set(False)
    gui.inv_freq_mode_var.set('Discrete list');gui.inv_freq_list_var.set('10')
    gui.inv_angle_start_var.set('0');gui.inv_angle_stop_var.set('0')
    gui.inv_requirement_db_var.set('-20')
    gui.robust_settings.restore(SETUP)
    state=gui._collect_project_state()
    gui._apply_project_state(state)
    assert gui.inv_wave_pol_var.get()=='Both' and gui.robust_settings.capture()==SETUP
    def sync(name,worker,success,error): success(worker())
    with mock.patch.object(gui,'_run_background_task',side_effect=sync), mock.patch('ibc.ui.messagebox.showerror',side_effect=AssertionError):
        gui._run_inverse_design()
    assert gui.inv_results_list.horizontalHeaderItem(2).text()=='Failure (%)'
    assert gui.inv_results_list.isColumnHidden(8)
    assert 'modeled' in gui.inv_requirement_status.text().lower()
    gui._open_inverse_verification()
    dialog=gui._inverse_verification_dialog
    with mock.patch.object(gui,'_run_background_task',side_effect=sync): dialog.run()
    dialog.update_progress()
    assert len(dialog.result['candidates'])==3 and dialog.export_button.isEnabled()
    assert dialog.result['polarizations']==['te','tm']
    dialog.select_candidate()
    assert not dialog.isVisible()

def test_invalid_sampling_setup_does_not_start_gui_job(gui):
    gui.layers=screen()
    gui.inv_score_mode_var.set(INVERSE_SCORE_YIELD)
    gui.robust_settings.fields['seed'].setText('invalid')
    with mock.patch.object(gui,'_run_background_task') as start, mock.patch('ibc.ui.messagebox.showerror') as error:
        gui._run_inverse_design()
    assert error.called and not start.called and not gui._inverse_active

def test_verification_report_export_and_source_change(tmp_path):
    import json
    from ibc.io import write_material_table
    from ibc.compute import MaterialTable
    from ibc.tolerance_analysis import export_tolerance_report
    configs=screen()
    path=tmp_path/'air.csv'
    table=MaterialTable([9.,11.],[1+0j]*2,[1+0j]*2)
    write_material_table(path,table)
    configs[1]=replace(configs[1],material_source='file',file_0deg=str(path))
    cand=candidate(configs)
    report=verify_candidates(configs,[cand],[10.],[0.],'te',CFG,-20,SETUP)
    output=tmp_path/'verification.json'
    export_tolerance_report(output,report)
    assert json.loads(output.read_text())==report
    changed=[False]
    def progress(*a):
        if not changed[0]:
            write_material_table(path,MaterialTable([9.,11.],[1.01+0j]*2,[1+0j]*2))
            changed[0]=True
    with pytest.raises(ValueError,match='Material files changed'):
        verify_candidates(configs,[cand],[10.],[0.],'te',CFG,-20,SETUP,progress=progress)

def test_real_background_verification_and_stop_preserve_report(gui):
    import time
    gui.layers=screen()
    gui.inv_wave_pol_var.set('Both')
    gui.inv_uncertainty_var.set(False)
    gui.inv_freq_mode_var.set('Discrete list');gui.inv_freq_list_var.set('10')
    gui.inv_angle_start_var.set('0');gui.inv_angle_stop_var.set('0')
    gui.robust_settings.restore(SETUP)
    app=QApplication.instance()
    def wait():
        deadline=time.monotonic()+15
        while gui.job_is_running() and time.monotonic()<deadline:
            app.processEvents();time.sleep(.01)
        assert not gui.job_is_running()
        app.processEvents()
    with mock.patch('ibc.ui.messagebox.showerror',side_effect=AssertionError):
        gui._run_inverse_design();wait()
        gui._open_inverse_verification()
        dialog=gui._inverse_verification_dialog
        dialog.run();wait();dialog.update_progress()
        saved=dialog.result
        assert saved and dialog.export_button.isEnabled()
        # Exercise cooperative cancellation through the real job contract.
        original=verify_candidates
        def cancelled(*a,**kw):
            dialog.stop_event.set()
            return original(*a,**kw)
        with mock.patch('ibc.robust_ui.verify_candidates',side_effect=cancelled):
            dialog.run();wait();dialog.update_progress()
        assert dialog.result is saved and not dialog.active and dialog.run_button.isEnabled()
        assert 'Stopped' in dialog.status.text()
        dialog.close()
