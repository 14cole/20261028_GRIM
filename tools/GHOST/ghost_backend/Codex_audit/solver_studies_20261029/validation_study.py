"""Independent-series accuracy and repeated-request lifecycle experiments."""
import gc
import json
import os
from pathlib import Path
import threading
import time
from unittest import mock
import numpy as np
import psutil
from study import save


def settings(mode='compressed'):
    return dict(factorization=mode,mesh_strategy='adaptive',basis_order=1,mesh_grading=True,
        assembly_threads=4,blas_threads=4,ram_budget_gib=12,angle_batch_size=16,rhs_compression='off')


def accuracy(case,directory):
    from test_2d_capability_acceptance import _circle
    from ghost_backend.twod import solver
    from ghost_backend.validation import cylinder
    kind=case['kind'];radius=case.get('radius',.1);count=case.get('chords',512)
    eps=2.5-.05j;inner=radius-.0005
    snapshot=dict(segments=[_circle(kind,radius,count,2 if kind=='pec' else 3,pos=0 if kind=='pec' else 1)],
                  ibcs=[],dielectrics=[] if kind=='pec' else [['1','2.5','-.05','1','0']])
    if kind=='coated':snapshot['segments'].append(_circle('core',inner,count,4,pos=1))
    frequency=case.get('frequency',15.)
    if case.get('resonance_offset') is not None:
        from scipy.special import jn_zeros
        frequency=float(jn_zeros(0,10)[-1])*(1+case['resonance_offset'])*solver.C0/(2*np.pi*radius*1e9)
    request=dict(geometry_snapshot=snapshot,frequencies_ghz=[frequency],elevations_deg=[0.,37.,90.,180.],
        geometry_units='meters',max_panels=30000,solver_method='experimental_cpu')
    save(directory/'request.json',dict(case=case,request=request))
    rows=[];all_fields={}
    for mode in case.get('modes',['dense','compressed']):
        started=time.perf_counter()
        # Exercise the hierarchical path on small analytical fixtures.
        with mock.patch.dict(os.environ,{'GHOST_HMATRIX_MIN_UNKNOWNS':'100'}):
            result=solver.solve_monostatic_rcs_2d_certified(**request,execution_options=settings(mode))
        metadata=result['metadata'];save(directory/(mode+'_metadata.json'),metadata)
        row=dict(mode=mode,seconds=time.perf_counter()-started,quality=metadata['quality_gate']['passed'],
                 mesh_certified=metadata['mesh_convergence_certified'],polarizations={})
        assert row['quality'] and row['mesh_certified']
        for export,pol in [('VV','TE'),('HH','TM')]:
            values=result['co_solved_samples'][export]
            fields=np.array([complex(r['rcs_amp_real'],r['rcs_amp_imag']) for r in values])
            all_fields[mode+'_'+export]=fields
            actual=np.array([r['rcs_linear'] for r in values])
            if kind=='pec':
                amplitude=cylinder.pec_cylinder_backscatter_amplitude(radius,frequency*1e9,pol)
                ref=cylinder.sigma_pec_cylinder(radius,frequency*1e9,pol)
                complex_error=float(np.max(abs(fields-amplitude))/abs(amplitude))
            else:
                ref=(cylinder.sigma_dielectric_cylinder(radius,eps,1,frequency*1e9,pol) if kind=='dielectric'
                     else cylinder.sigma_coated_pec_cylinder(inner,radius,eps,1,frequency*1e9,pol))
                complex_error=None
            error_db=float(np.max(abs(10*np.log10(actual/ref))))
            row['polarizations'][pol]=dict(max_rcs_error_db=error_db,max_complex_relative_error=complex_error,
                                           series_rcs=ref)
            assert np.isfinite(error_db) and error_db<.05, row
            if complex_error is not None:assert complex_error<.005,row
        rows.append(row)
        save(directory/'accuracy_progress.json',rows)
    np.savez(directory/'fields.npz',**all_fields)
    return dict(case=case,status='passed',frequency_ghz=frequency,ka=2*np.pi*frequency*1e9*radius/solver.C0,
        qualification='Certified polygon meshes compared against independent circular-wave series; circle chord error remains.',
        limits=dict(rcs_db=.05,pec_complex_relative=.005),results=rows)


def lifecycle(case,directory):
    from test_experimental_cpu import fixture,fields
    from ghost_backend.twod import solver
    from ghost_backend.compressed import preconditioner_hints,worker_pool
    from ghost_backend.twod.preparation import run_resources
    from ghost_backend.execution.metrics import active_metrics
    from ghost_backend.compressed.hmatrix_factor import HMatrixFactor
    from ghost_backend.compressed.hmatrix import HMatrixOperator
    process=psutil.Process();snapshot=fixture('coated',192)
    base=dict(geometry_snapshot=snapshot,frequencies_ghz=[.6],elevations_deg=[0.,37.,90.],
        geometry_units='meters',solver_method='experimental_cpu',compute_condition_number=True,
        execution_options=dict(settings(),mesh_strategy='global',basis_order=1))
    baseline={};records=[]
    scratch=Path(os.environ['TEMP'])
    initial_temp={str(p.relative_to(scratch)) for p in scratch.rglob('*')}
    def record(label):
        gc.collect(); info=process.memory_info()
        live=[p.pid for p in process.children(recursive=True) if p.is_running()]
        row=dict(label=label,rss=info.rss,private=getattr(info,'private',None),children=live,
            hints_cleared=preconditioner_hints._CURRENT.get() is None,run_scope_cleared=run_resources() is None,
            metrics_cleared=active_metrics() is None,worker_reserved=worker_pool.retained_bytes(),
            extra_temp_paths=sorted({str(p.relative_to(scratch)) for p in scratch.rglob('*')}-initial_temp))
        row['solver_threads']=[t.name for t in threading.enumerate()
            if t.name.startswith(('ghost-hmatrix','GHOST memory sampler'))]
        assert row['hints_cleared'] and row['run_scope_cleared'] and row['metrics_cleared'] and row['worker_reserved']==0
        assert not live,row
        assert not row['extra_temp_paths'],row
        assert not row['solver_threads'],row
        records.append(row);save(directory/'lifecycle_progress.json',records)
    record('baseline')
    with mock.patch.dict(os.environ,{'GHOST_HMATRIX_MIN_UNKNOWNS':'100'}):
        for repetition in range(5):
            for frequency in (.6,.8,1.):
                result=solver.solve_monostatic_rcs_2d(**dict(base,frequencies_ghz=[frequency]))
                assert result['metadata']['quality_gate']['passed']
                values={pol:fields(result,pol) for pol in ('VV','HH')}
                if frequency not in baseline:baseline[frequency]=values
                else:
                    for pol in values:np.testing.assert_allclose(values[pol],baseline[frequency][pol],rtol=1e-10,atol=1e-12)
                del result,values
                record(f'pass_{repetition}_{frequency}')
        # Deterministic cancellation at numerical stage boundaries uses the
        # actual abort event/checkpoint, not a fabricated numerical rejection.
        stages=[('assembly',HMatrixOperator,'__init__'),('factorization',HMatrixFactor,'_build'),
                ('angle_solve',HMatrixFactor,'solve')]
        for label,module,name in stages:
            abort=threading.Event();original=getattr(module,name);observed=[]
            def interrupted(*args,**kwargs):
                observed.append(True);abort.set();return original(*args,**kwargs)
            try:
                with mock.patch.object(module,name,interrupted):
                    solver.solve_monostatic_rcs_2d(**dict(base,abort_event=abort))
            except InterruptedError:pass
            else:raise AssertionError('Cancellation did not propagate at '+label)
            assert observed,label
            record('cancel_'+label)
            result=solver.solve_monostatic_rcs_2d(**base)
            for pol in ('VV','HH'):np.testing.assert_allclose(fields(result,pol),baseline[.6][pol],rtol=1e-10,atol=1e-12)
            del result;record('restart_'+label)
    warm=[r['rss'] for r in records if r['label'].startswith('pass_')][3:]
    return dict(case=case,status='passed',completed_sweep_solves=15,cancel_restart_pairs=3,
        post_warm_rss_span_bytes=max(warm)-min(warm),records=records,
        scope='Small coated fixture, real field equality and context/child cleanup; not proof of no leak at every size.')


def execute(case,directory):
    return {'accuracy':accuracy,'lifecycle':lifecycle}[case['task']](case,directory)
