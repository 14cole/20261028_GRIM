"""Independent Line Expansion checks; use the audited GHOST tree on PYTHONPATH.

Synthetic coefficients isolate expansion/export from section-solver physics.
The separate real_gui_solve.py exercises the unmodified solver and Qt worker.
"""
import importlib
import json
import math
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PySide6.QtWidgets import QApplication, QLabel
from ghost_backend.ui.line_expansion import LineExpansionTab, parse_samples
from ghost_backend.assembly.line_expansion import SeamCoefficients, expand_perimeter, C0
from ghost_backend.assembly.fields import export_radar_grim
from ghost_backend.data_tools.cem_tools.native_samples import decode_native_samples, raw_amplitude
from ghost_backend.io.grim import _save_grim_npz

wing = importlib.import_module('ghost_backend.assembly.expand_wing_sections')
results = []
def record(name, status, details=None):
    results.append(dict(name=name, status=status, details=details))
    print(status.upper(), name, json.dumps(details) if details is not None else '', flush=True)
def check(name, condition, details=None):
    if not condition:
        raise AssertionError((name, details))
    record(name, 'pass', details)
def error(call):
    try:
        call()
    except Exception as exc:
        return type(exc).__name__ + ': ' + str(exc)
    return None
def payload(path):
    with np.load(path, allow_pickle=False) as stored:
        return decode_native_samples({k: stored[k] for k in stored.files})
def constant_coefficients(snapshot, frequency, angles, **kwargs):
    # Native TM phase conversion is 180 degrees. Both electric responses = 1.
    return SeamCoefficients(frequency, angles, np.full(len(angles), -4*math.pi),
                            np.full(len(angles), 4*math.pi))

app = QApplication.instance() or QApplication([])
tab = LineExpansionTab(); tab.resize(1100, 850); tab.show(); app.processEvents()
with tempfile.TemporaryDirectory(prefix='line-audit-') as work:
    root = Path(work)
    geo = root/'section.geo'
    geo.write_text('Title: strip\nSegment: strip\nproperties: 2 10 0 0 0\n-0.01 0 0.01 0\nIBCS_Resistances:\nDielectrics:\n')
    section = dict(geometry=str(geo), root=(0,0,0), tip=(0.2,0,0), normal=(0,0,1))
    settings = dict(coordinate_units='meters', geometry_units='meters',
                    frequencies_ghz=[0.3], azimuths_deg=[0,45,90], elevations_deg=[20],
                    section_angle_step_deg=30, shadow=False)
    def run(name, sections=None, **options):
        args=dict(settings); args.update(options)
        return wing.expand_wing_sections(sections or [section], output_grim=str(root/(name+'.grim')), **args)

    check('sample parser list and inclusive aligned sweep',
          parse_samples('1, 2 3','f') == (1,2,3) and parse_samples('0:1:0.25','a') == (0,.25,.5,.75,1))
    for raw in ('nan', '1,1', '2,1', '0:1:0', '0:1:-1', '1:0:1'):
        check('reject malformed sweep '+raw, error(lambda: parse_samples(raw,'grid')) is not None)
    overflow = error(lambda: parse_samples('0:1e308:1e-308','grid'))
    record('sweep arithmetic overflow escapes GUI ValueError handler', 'deficiency', overflow)
    started=time.perf_counter(); many=parse_samples('0:100000:1','azimuth'); elapsed=time.perf_counter()-started
    record('sweep materializes on GUI thread without sample budget', 'observation', dict(samples=len(many),seconds=elapsed))
    check('section step rejects nondivisor before solve', error(lambda: wing._section_angles(7)) is not None)
    for key,value in [('tip',(0,0,0)),('normal',(0,0,0)),('normal',(1,0,0)),('normal_end',(0,0,-1)),('root',(float('nan'),0,0))]:
        bad=dict(section); bad[key]=value
        check('reject invalid station '+key+str(value), error(lambda: wing._stations([bad],'meters',False,root)) is not None)
    path=root/'path.csv';path.write_text('# points\n0,0,0\n1,0,0,0,0,1\n2,1,0\n')
    chain=wing.sections_from_path(str(geo),*wing.read_path_points(path))
    check('path import chains endpoints and defaults normal',len(chain)==2 and chain[0]['tip']==chain[1]['root'] and chain[0]['normal']==(0,0,1))
    for units,scale in [('meters',1),('millimeters',.001),('inches',.0254),('feet',.3048)]:
        stations=wing._stations([section],units,True,root)
        check('placement units and mirrored handedness '+units,
              np.allclose(np.linalg.norm(stations[0][2][1]-stations[0][2][0]),.2*scale)
              and np.allclose(stations[1][2],stations[0][2][::-1]*[1,-1,1]))

    # Independent closed-form integral of a uniform straight line.
    f=.3; k=2*math.pi*f*1e9/C0; length=.2
    seg=np.array([[.07,-length/2,.03],[.07,length/2,.03]])
    normals=np.array([[1.,0,0],[1.,0,0]])
    directions=np.array([[1,0,0],[-1,0,0],[.8,.3,.4],[-.8,.3,.4],[.8,-.4,.2]])
    directions/=np.linalg.norm(directions,axis=1)[:,None]
    table=constant_coefficients(None,f,[0,90,180])
    field=wing._station_field([(table,table)],[f],seg,normals,f,directions,180,0,None,None)
    oracle=length*np.sinc(k*length*directions[:,1]/math.pi)*np.exp(2j*k*(directions@seg.mean(axis=0)))
    check('uniform line analytic sinc, phase, both half-spaces and polarization',
          np.allclose(field['F_vv'],oracle,atol=2e-14) and np.allclose(field['F_hh'],oracle,atol=2e-14)
          and np.max(abs(field['F_vh']))<2e-14,
          dict(max_abs_error=float(max(np.max(abs(field[q]-oracle)) for q in ('F_vv','F_hh')))))
    def asymmetric(snapshot, frequency, angles, **kwargs):
        amplitude=2+np.cos(np.deg2rad(angles))+.2*np.sin(np.deg2rad(angles))
        return SeamCoefficients(frequency,angles,-4*math.pi*amplitude,4*math.pi*amplitude)
    with patch.object(wing,'coefficients_from_2d',side_effect=asymmetric):
        half_tables=wing._half_space_tables(str(geo),f,f,wing._section_angles(30),'meters',{}, {})
    asymmetric_field=wing._station_field([half_tables],[f],seg,normals,f,directions[:2],180,0,None,None)
    check('asymmetric section maps opposite sides to 90 and 270 degrees',
          np.allclose(asymmetric_field['F_vv'],oracle[:2]*[2.2,1.8],atol=2e-14))
    shifted=seg+np.array([.04,-.02,.03])
    translated=wing._station_field([(table,table)],[f],shifted,normals,f,directions,180,0,None,None)
    phase=np.exp(2j*k*(directions@np.array([.04,-.02,.03])))
    check('translation obeys two-way phase',np.allclose(translated['F_vv'],field['F_vv']*phase,atol=2e-14))
    split=sum((wing._station_field([(table,table)],[f],s,normals,f,directions,180,0,None,None)['F_vv']
               for s in (np.array([seg[0],seg.mean(axis=0)]),np.array([seg.mean(axis=0),seg[1]]))))
    check('splitting a straight station preserves field',np.allclose(split,field['F_vv'],atol=2e-14))
    twisted=normals.copy();twisted[1]=[math.sqrt(.5),0,math.sqrt(.5)]
    twist_field=wing._station_field([(table,table)],[f],seg,twisted,f,directions,180,0,None,None)
    check('twisted frame preserves isotropic line response',np.allclose(twist_field['F_vv'],oracle,atol=2e-14))
    reduced=[.15,.3];table_sets=[]
    for frequency in reduced:
        t=constant_coefficients(None,f,[0,90,180]);t.dA_tm*=frequency;t.dA_te*=frequency
        table_sets.append((t,t))
    oblique_field=wing._station_field(table_sets,reduced,seg,normals,f,directions,180,0,None,None)
    transverse=np.clip(f*np.sqrt(1-directions[:,1]**2),.15,.3)
    check('oblique interpolation uses transverse frequency',np.allclose(oblique_field['F_vv'],oracle*transverse,atol=2e-14))
    rng=np.random.default_rng(20261110); looks=rng.normal(size=(79,3));looks[:,0]=abs(looks[:,0])+.1;looks/=np.linalg.norm(looks,axis=1)[:,None]
    common=dict(segment_normals=normals[None,:,:],grazing_taper_deg=0,frequency_ghz=f)
    scalar=expand_perimeter(seg[None,:,:],table,None,looks,_look_batch_size=1,**common)
    batch=expand_perimeter(seg[None,:,:],table,None,looks,_look_batch_size=32,**common)
    check('scalar and batched expansion agree',all(np.allclose(scalar[q],batch[q],atol=2e-14) for q in scalar))
    class HalfShadow:
        def visible_line_intervals(self, starts, ends, direction, **kw):
            return np.arange(len(starts)), np.zeros(len(starts)),np.full(len(starts),.5)
    shadowed=expand_perimeter(seg[None,:,:],table,None,np.array([[1.,0,0]]),occluder=HalfShadow(),**common)
    check('exact half-visible line integrates half amplitude',np.allclose(shadowed['F_vv'],.5*oracle[0],atol=2e-14))

    with patch.object(wing,'coefficients_from_2d',side_effect=constant_coefficients) as solve:
        good=run('good'); data=payload(good['output']); amp=raw_amplitude(data)
        check('sections-only archive roundtrip finite field',amp.shape==(3,1,1,3) and np.all(np.isfinite(amp)))
        check('archive power matches complex field',np.allclose(np.asarray(data['rcs_power']),4*math.pi*abs(amp)**2,rtol=2e-7))
        check('one solve reused for identical section files', (run('cached',[section,dict(section,root=(.2,0,0),tip=(.4,0,0))]) is not None) and solve.call_count==2)
        before=Path(good['output']).read_bytes()
        cancel=error(lambda: run('good',cancel_check=lambda:True))
        check('early cancellation retains output and removes stage',cancel.startswith('InterruptedError') and Path(good['output']).read_bytes()==before and not list(root.glob('.*tmp*')))
        failure=error(lambda:run('good',section_angle_step_deg=7))
        check('validation failure retains existing output',failure is not None and Path(good['output']).read_bytes()==before)
        base_options=dict(body_grim=good['output'],frequencies_ghz=None,azimuths_deg=None,elevations_deg=None)
        combined=run('combined',**base_options); combined_data=payload(combined['output'])
        check('base plus identical section sums coherently',np.allclose(raw_amplitude(combined_data),2*amp,atol=2e-14))
        check('base grid conflict rejected',error(lambda:run('badgrid',**dict(base_options,frequencies_ghz=[.3]))) is not None)
        check('base overwrite rejected',error(lambda:run('good',**base_options)) is not None)
        mirrored=run('mirror',mirror=True)
        explicit_mirror=dict(section,root=(-.2,0,0),tip=(0,0,0))
        explicit=run('explicit_mirror',[section,explicit_mirror])
        check('mirror option equals explicit reflected station',np.allclose(raw_amplitude(payload(mirrored['output'])),raw_amplitude(payload(explicit['output'])),atol=2e-14))
        # Exercise the actual BoR occluder on a line inside a closed body.
        body=dict(data);body['body_profile_rho_m']=np.array([0,.1,.1,0])
        body['body_profile_z_m']=np.array([.1,.1,-.1,-.1]);body['body_profile_kind']=np.asarray('outer_boundary')
        bodypath=root/'body.grim';_save_grim_npz(body,str(bodypath))
        buried=dict(section,root=(-.04,0,0),tip=(.04,0,0))
        shadow_error=error(lambda:run('hidden',[buried],**dict(base_options,body_grim=str(bodypath),shadow=True)))
        record('embedded BoR shadowing crashes across BVH leaves','deficiency' if shadow_error else 'pass',shadow_error)
        crossing=dict(section,root=(.05,0,0),tip=(.15,0,0))
        crossing_error=error(lambda:run('crossing',[crossing],**dict(base_options,body_grim=str(bodypath),shadow=True)))
        record('body-crossing root line shadowing','deficiency' if crossing_error else 'pass',crossing_error)
        body['body_profile_kind']=np.asarray('transmitting_sheet');_save_grim_npz(body,str(bodypath))
        check('transmitting sheet cannot supply opaque shadowing',error(lambda:run('sheet',[buried],**dict(base_options,body_grim=str(bodypath),shadow=True))) is not None)
        bad_corner=dict(fold_start=(0,0,0),fold_end=(0,0,0),n_wing=(0,0,1),n_body=(1,0,0),face_width=.1)
        check('invalid corner rejected without replacing output',error(lambda:run('good',corners=[bad_corner])) is not None and Path(good['output']).read_bytes()==before)
        # Both reciprocal cross-polarized channels are a valid imported layout.
        four=dict(data); four['polarizations']=np.array(['VV','HH','VH','HV'])
        four_amp=np.zeros((3,1,1,4),complex)
        four['rcs_amp_real']=four_amp.real;four['rcs_amp_imag']=four_amp.imag
        four['rcs_power']=np.zeros(four_amp.shape);four['rcs_phase']=np.zeros(four_amp.shape)
        fourpath=root/'four.grim';_save_grim_npz(four,str(fourpath))
        tilted=dict(section,normal=(0,1,1))
        # Unequal local channels create an observable cross-polarized field.
        def anisotropic(*args,**kw):
            c=constant_coefficients(*args,**kw);c.dA_te*=2;return c
        with patch.object(wing,'coefficients_from_2d',side_effect=anisotropic):
            cross=run('cross',[tilted],**dict(base_options,body_grim=str(fourpath)))
        crossamp=raw_amplitude(payload(cross['output']))
        record('four-channel base updates VH but leaves HV unchanged','deficiency',
               dict(max_VH=float(np.max(abs(crossamp[...,2]))),max_HV=float(np.max(abs(crossamp[...,3])))))
        # Explicitly incompatible imported metadata is accepted by this loader.
        for label,update in [('radian_axes',{'units':json.dumps(dict(json.loads(str(data['units'])),azimuth='rad',elevation='rad'))}),
                             ('opposite_time_sign',{'time_convention':'exp(-jwt)'}),
                             ('polar_theta',{'units':json.dumps(dict(json.loads(str(data['units'])),angular_coordinate_system='theta_phi',elevation_coordinate_convention='sentri_theta_top_zero'))})]:
            modified=dict(data);modified.update(update);bp=root/(label+'.grim');_save_grim_npz(modified,str(bp))
            outcome=error(lambda:run(label+'_out',**dict(base_options,body_grim=str(bp))))
            loaded=payload(bp)
            check('incompatible '+label+' metadata survived fixture serialization',all(str(loaded[k])==str(v) for k,v in update.items()))
            record('base metadata '+label+' accepted without conversion','deficiency' if outcome is None else 'observation',outcome)
        # Warnings should travel with the deliverable, not only the GUI status.
        warning_run=run('warning',section_angle_step_deg=90,frequencies_ghz=[3.])
        warning_data=payload(warning_run['output'])
        provenance=json.loads(str(warning_data['line_expansion_provenance_json'])) if 'line_expansion_provenance_json' in warning_data else None
        record('output provenance omits reproducible placement, settings and warnings','deficiency',
               dict(warnings=warning_run['warnings'],provenance=provenance,history=str(warning_data['history'])))
        # Cancellation arriving during final serialization is not checked again.
        stop=threading.Event(); original_save=_save_grim_npz
        late_destination=root/'late_cancel.grim';late_destination.write_bytes(b'existing output')
        def save_then_cancel(*args,**kwargs):
            result=original_save(*args,**kwargs);stop.set();return result
        import ghost_backend.io.grim as gio
        with patch.object(gio,'_save_grim_npz',side_effect=save_then_cancel):
            late=run('late_cancel',cancel_check=stop.is_set,**base_options)
        record('cancel during final save still replaces destination','deficiency',dict(saved=Path(late['output']).exists(),replaced_existing=late_destination.read_bytes()!=b'existing output',cancel_requested=stop.is_set()))

    # Examine the actual handoff to the 2-D solver; this test does not solve EM.
    captured={}
    def fake_2d(**kwargs):
        captured.update(kwargs)
        return {'co_solved_samples':{p:[dict(theta_inc_deg=a,rcs_amp_real=1,rcs_amp_imag=0) for a in kwargs['elevations_deg']] for p in ('VV','HH')}}
    with patch('ghost_backend.twod.solver.solve_monostatic_rcs_2d_certified',side_effect=fake_2d):
        run('solver_args')
    record('section solve uses certified entry and receives no abort/progress callback','deficiency',
           dict(argument_keys=sorted(captured),abort_event=repr(captured.get('abort_event')),progress_callback=repr(captured.get('progress_callback'))))
    check('blank GUI end normal retains starting normal',not tab.job_is_running())
    tab._append_row([str(geo),'0','0','0','.2','0','0','0','0','1','','',''])
    check('GUI serializes section inputs',tab.sections()==[section])
    tab.section_table.clearSelection();tab._remove_sections()
    check('GUI no-selection removal keeps rows',tab.section_table.rowCount()==1)
    tab._set_busy(True)
    check('GUI locks every input while running',all(not w.isEnabled() for w in tab._input_widgets) and not tab.run_button.isEnabled() and tab.cancel_button.isEnabled())
    tab._set_busy(False)
    help_text=' '.join(w.text() for w in tab.findChildren(QLabel))
    record('help contradicts shadow and corner options','deficiency',dict(no_shadowing_claim='no coupling or shadowing' in help_text,shadow_default=tab.shadow.isChecked(),corner_help='double bounce' in help_text))
    tab.grab().save(str(Path(__file__).with_name('line-expansion-tab.png')))
    check('GUI screenshot saved',Path(__file__).with_name('line-expansion-tab.png').is_file())

Path(__file__).with_name('audit-results.json').write_text(json.dumps(results,indent=2))
print('TOTAL',len(results),flush=True)
