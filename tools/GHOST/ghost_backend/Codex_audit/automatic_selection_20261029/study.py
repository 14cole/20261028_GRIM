"""Bounded, serial, isolated studies; no production policy changes."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT.parent), str(ROOT / 'tests')]


def save(path, data):
    path.write_text(json.dumps(data, indent=2, default=lambda x: x.tolist() if hasattr(x, 'tolist') else str(x)), encoding='utf-8')


def geometry(name, coating_thickness=.125):
    spec = importlib.util.spec_from_file_location('prior_probe', HERE.parent / 'followups_20261029/capacity_probe.py')
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    if name not in ('coated_inlet', 'dogleg'):
        return prior.geometry(name)
    base = prior.geometry('inlet_dielectric' if name == 'coated_inlet' else 'inlet')
    if name == 'coated_inlet':
        # 1/8-inch dielectric shell around the solid metal contour, including
        # the notch walls. It is not material filling an empty inlet cavity.
        t = coating_thickness
        points = [(t,t),(144-t,t),(144-t,12-t),(96-t,12-t),
                  (96-t,24+t),(144-t,24+t),(144-t,36-t),(t,36-t)]
        base['dielectrics'] = [['1','2.5','-.05','1','0']]
        kind = 4
    else:
        points = [(0,0),(144,0),(144,12),(96,12),(96,6),(48,6),
                  (48,18),(84,18),(84,24),(144,24),(144,36),(0,36)]
        kind = 2
    points = list(reversed(points)); points.append(points[0])
    segment = dict(name=name,seg_type=kind,properties=[str(kind),'-20','0','1' if kind==4 else '0','0'],
        point_pairs=[dict(x1=a[0],y1=a[1],x2=b[0],y2=b[1]) for a,b in zip(points[:-1],points[1:])])
    if name == 'coated_inlet':
        base['segments'].append(segment)
    else:
        base['segments'] = [segment]
    return base


def worker(case, directory):
    if case.get('switch_after_steps') is not None:
        import inspect
        import textwrap
        from ghost_backend.twod import adaptivity
        def choose(selection, step):
            wanted='dense' if step<case['switch_after_steps'] else 'compressed'
            admitted=[selection['selected']]+list(selection.get('retry_order',[]))
            if wanted not in admitted:raise MemoryError('Audit transition backend not admitted: '+wanted)
            return dict(selection,selected=wanted,retry_order=[m for m in admitted if m!=wanted],
                reason='Audit-only prescribed transition among admitted candidates.',
                audit_transition=dict(step=step,selected=wanted,after_steps=case['switch_after_steps']))
        source=textwrap.dedent(inspect.getsource(adaptivity._run_certified))
        needle="            selected_options['factorization'] = selection['selected']"
        assert source.count(needle)==1
        source=source.replace(needle,"            selection = AUDIT_CHOOSE(selection, len(steps))\n"+needle)
        namespace=dict(vars(adaptivity),AUDIT_CHOOSE=choose)
        exec(compile(source,'<audit_prescribed_transition>','exec'),namespace)
        adaptivity._run_certified=namespace['_run_certified']
    if case.get('diagnose_condition'):
        from ghost_backend.twod import solver
        original=solver.evaluate_quality_gate
        gate_records=[]
        def diagnostic_gate(metadata, thresholds=None):
            original_gate=original(metadata,thresholds)
            gate_records.append(dict(gate=original_gate,panels=metadata.get('panel_count'),
                nodes=metadata.get('linear_node_count'),unknowns=metadata.get('dense_largest_system'),
                polarization=metadata.get('polarization'),degree=metadata.get('polynomial_degree')))
            save(directory/'original_quality_gates.json',gate_records)
            return original(metadata,dict(thresholds or {},condition_est_max=1e99))
        solver.evaluate_quality_gate=diagnostic_gate
    if case.get('task'):
        if case['task']=='prototype':
            from capacity_prototype import execute
        else:
            from validation_study import execute
        try:
            record=execute(case,directory)
        except Exception as exc:
            record=dict(case=case,status='rejected',error_type=type(exc).__name__,error=str(exc))
            traceback.print_exc()
        save(directory/'result.json',record)
        print(json.dumps(record,default=str),flush=True)
        return
    import numpy as np
    dense_leaf_events=[]
    if case.get('experimental_dense_leaf_limit'):
        # Offline ablation of the existing rejected-block dense-leaf fallback.
        # 1024 complex128 entries per side stays within the 16 MiB query cap.
        # No production source, accuracy threshold, or admission budget changes.
        import inspect
        import textwrap
        from ghost_backend.compressed import inverse
        assert case['experimental_dense_leaf_limit']==1024
        source=textwrap.dedent(inspect.getsource(inverse.CompressedSystem.build))
        assert source.count('if len(ids)>512:raise')==1
        source=source.replace('if len(ids)>512:raise','if len(ids)>1024:raise')
        assert source.count('node.leaf=True')==1
        source=source.replace('node.leaf=True',"node.leaf=True\n            AUDIT_DENSE_LEAF_EVENTS.append(dict(size=len(ids),tolerance=self.tolerance,system_unknowns=self.n))")
        namespace=dict(vars(inverse),AUDIT_DENSE_LEAF_EVENTS=dense_leaf_events)
        exec(compile(source,'<audit_dense_leaf_1024>','exec'),namespace)
        inverse.CompressedSystem.build=namespace['build']
    from ghost_backend.execution.options import validate_options
    from ghost_backend.execution.selection import select_backend
    from ghost_backend.execution.metrics import progress_listener
    from ghost_backend.execution.diagnostics import diagnostic_scope, mark_uncertified
    from ghost_backend.twod.solver import solve_monostatic_rcs_2d_certified
    if case.get('disable_hint'):
        from ghost_backend.compressed import preconditioner_hints
        preconditioner_hints.try_build = lambda factor: False
    options = validate_options(dict(factorization=case['mode'], mesh_strategy='adaptive', basis_order=1,
        mesh_grading=True, assembly_threads=4, blas_threads=4, ram_budget_gib=case.get('ram',24),
        compressed_storage_mib=0, angle_batch_size=256, rhs_compression='auto'))
    request = dict(geometry_snapshot=geometry(case['geometry'],case.get('coating_thickness',.125)), frequencies_ghz=[case['frequency']],
        elevations_deg=list(range(361)), geometry_units='inches', max_panels=100000)
    save(directory / 'request.json',dict(case=case,request=request,options=options))
    record = dict(case=case,options=options)
    events = (directory / 'stage_events.jsonl').open('w',encoding='utf-8')
    def event(value):
        events.write(json.dumps(value)+'\n'); events.flush()
    started = time.perf_counter()
    try:
        record['initial_forecast'] = select_backend(request,options,certified=True)
        record['planning_seconds'] = time.perf_counter()-started
        started = time.perf_counter()
        relaxed = dict(condition_est_max=1e99) if case.get('diagnose_condition') else {}
        with diagnostic_scope(relaxed), progress_listener(event):
            result = solve_monostatic_rcs_2d_certified(**request,solver_method='experimental_cpu',execution_options=options)
        record['solve_seconds'] = time.perf_counter()-started
        metadata = result['metadata']
        if relaxed:
            metadata = mark_uncertified(metadata, relaxed)
        save(directory / 'metadata.json', metadata)
        np.savez(directory / 'fields.npz',**{p:np.asarray([complex(r['rcs_amp_real'],r['rcs_amp_imag']) for r in rows])
            for p,rows in result['co_solved_samples'].items()})
        record.update(status='passed',quality_passed=metadata['quality_gate']['passed'],
            mesh_certified=metadata['mesh_convergence_certified'],actual_options=metadata['execution_options'])
        if case.get('diagnose_condition'):
            record.update(status='diagnostic',uncertified=True,
                note='Audit-only condition threshold relaxed; original gates saved. Not a certified capacity result.')
        else:
            assert record['quality_passed'] and record['mesh_certified']
    except Exception as exc:
        record.update(status='rejected',error_type=type(exc).__name__,error=str(exc),
                      elapsed_to_rejection_seconds=time.perf_counter()-started)
        traceback.print_exc()
    finally:
        events.close()
        save(directory / 'result.json',record)
        if case.get('experimental_dense_leaf_limit'):
            save(directory/'audit_dense_fallbacks.json',dense_leaf_events)
    print(json.dumps({k:record.get(k) for k in ('status','solve_seconds','error')}),flush=True)


def run(case):
    import psutil
    directory = HERE / 'runs' / case['name']
    if directory.exists():
        raise RuntimeError('Refusing to overwrite '+str(directory))
    directory.mkdir(parents=True)
    save(directory / 'case.json',case)
    temporary=HERE/'scratch'/case['name'];temporary.mkdir(parents=True,exist_ok=True)
    env = dict(os.environ, OPENBLAS_NUM_THREADS='4',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',
        PYTHONIOENCODING='utf-8',GHOST_DENSE_BACKEND='cpu',GHOST_LU_PRECISION='double',
        GHOST_TIMING_CACHE_DIR=str(HERE/'timing_cache'/case['name']),TEMP=str(temporary),TMP=str(temporary))
    # Every comparison starts with its own empty timing history. No shared
    # learned backend preferences can bias mode order across repetitions.
    started = time.monotonic(); stopped=None; peak_rss=peak_private=0
    available_start=psutil.virtual_memory().available; minimum_available=available_start
    with (directory/'worker.log').open('w',encoding='utf-8') as log:
        process=subprocess.Popen([sys.executable,'-u',str(Path(__file__).resolve()),'--worker',str(directory/'case.json')],
                                 cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        parent=psutil.Process(process.pid)
        while process.poll() is None:
            try:
                family=[parent]+parent.children(recursive=True)
                memory=[p.memory_info() for p in family]
                rss=sum(m.rss for m in memory); private=sum(getattr(m,'private',0) for m in memory)
                peak_rss=max(peak_rss,rss); peak_private=max(peak_private,private)
                available=psutil.virtual_memory().available; minimum_available=min(minimum_available,available)
                if max(rss,private)>24*1024**3:stopped='24 GiB process-tree RSS/private-commit guard'
                if available<2*1024**3:stopped='2 GiB host available-memory floor'
                if time.monotonic()-started>case.get('timeout',480):stopped='Per-case time guard'
                if stopped:
                    for child in reversed(family):
                        try:child.kill()
                        except psutil.NoSuchProcess:pass
                    process.wait();break
            except psutil.NoSuchProcess:pass
            time.sleep(.1)
    save(directory/'monitor.json',dict(returncode=process.returncode,stop_reason=stopped,
        peak_rss_bytes=peak_rss,peak_private_bytes=peak_private,host_available_start_bytes=available_start,
        host_available_minimum_bytes=minimum_available,elapsed_seconds=time.monotonic()-started,
        sampling_seconds=.1,scope='isolated process tree; RSS may double-count shared pages; private is Windows commit'))
    if stopped or not (directory/'result.json').exists():
        save(directory/'result.json',dict(case=case,status='stopped' if stopped else 'process_failed',error=stopped))
    result=json.loads((directory/'result.json').read_text())
    print(json.dumps(dict(name=case['name'],status=result['status'],seconds=result.get('solve_seconds'),
                         peak_rss_gib=peak_rss/1024**3,error=result.get('error'))),flush=True)


def initial_plan():
    return [dict(name=f'capacity_{g}_{f}ghz',geometry=g,frequency=f,mode='adaptive') for g,f in
        [('inlet_dielectric',3),('inlet_dielectric',10),('inlet_dielectric',15),
         ('coated_inlet',3),('coated_inlet',10),('coated_inlet',15),('dogleg',15)]]


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--worker');parser.add_argument('--plan')
    args=parser.parse_args()
    if args.worker:
        path=Path(args.worker);worker(json.loads(path.read_text()),path.parent)
    else:
        plan=json.loads(Path(args.plan).read_text()) if args.plan else initial_plan()
        for case in plan:run(case)
