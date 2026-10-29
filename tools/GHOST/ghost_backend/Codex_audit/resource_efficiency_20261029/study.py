"""Serial real-geometry throughput/capacity studies with unchanged certification."""
import argparse,importlib.util,json,os,subprocess,sys,time,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];GIB=1024**3
sys.path.insert(0,str(ROOT.parent))
def save(path,value):path.write_text(json.dumps(value,indent=2,default=lambda x:x.tolist() if hasattr(x,'tolist') else str(x))+'\n')
def geometry(name):
    spec=importlib.util.spec_from_file_location('geometry_source',HERE.parent/'solver_studies_20261029/study.py')
    source=importlib.util.module_from_spec(spec);spec.loader.exec_module(source)
    base=source.geometry('dogleg' if name.startswith('dogleg') else name)
    if name in ('dogleg_dielectric','dogleg_magnetic'):
        segment=base['segments'][0];segment.update(seg_type=3,properties=['3','-20','0','1','0'])
        base['dielectrics']=[['1','4','-.04','1','0']] if name=='dogleg_dielectric' else [['1','101.19','-11.88','3.45','-3.47']]
    return base

def worker(case,directory):
    import numpy as np,psutil
    from ghost_backend.twod.solver import solve_monostatic_rcs_2d_certified
    from ghost_backend.execution import memory_budget as mb,metrics
    from ghost_backend.execution.options import automatic_options,execution_scope,effective_assembly_threads,blas_thread_reservation
    options=automatic_options(ram_budget_gib=case.get('cap',12.))
    options['temporary_directory']=str(HERE/'scratch')
    if case['profile']=='four':options.update(assembly_threads=4,blas_threads=4)
    request=dict(geometry_snapshot=geometry(case['geometry']),frequencies_ghz=[case.get('frequency',15.)],
        elevations_deg=list(range(361)),geometry_units='inches',max_panels=100000)
    save(directory/'request.json',dict(case=case,request=request,options=options))
    phase=['prepare'];record=dict(case=case);process=psutil.Process();cpu_start=time.process_time();started=time.perf_counter()
    with (directory/'events.jsonl').open('w') as stream:
        def event(value):
            phase[0]=value['stage_key'];stream.write(json.dumps(value)+'\n');stream.flush()
        with execution_scope(options),mb.scope() as ledger:
            record['initial_execution']=dict(assembly_threads=effective_assembly_threads(),blas_reservation=blas_thread_reservation())
            try:
                with metrics.progress_listener(event):
                    result=solve_monostatic_rcs_2d_certified(**request,execution_options=options)
                record['solve_seconds']=time.perf_counter()-started
                metadata=result['metadata'];save(directory/'metadata.json',metadata)
                fields={p:np.asarray([complex(v['rcs_amp_real'],v['rcs_amp_imag']) for v in values]) for p,values in result['co_solved_samples'].items()}
                np.savez(directory/'fields.npz',**fields)
                reference=case.get('reference')
                if reference:
                    with np.load(HERE.parent/reference/'fields.npz') as prior:
                        errors={p:float(np.max(abs(values-prior[p]))/max(1.,float(np.max(abs(prior[p]))))) for p,values in fields.items()}
                    record['reference_relative_field_errors']=errors
                    assert max(errors.values())<1e-10,errors
                assert metadata['quality_gate']['passed'] and metadata['mesh_convergence_certified']
                record.update(status='passed',certified=True,linear_node_count=metadata.get('linear_node_count'),
                    stage_seconds=metadata.get('runtime_profile',{}).get('stage_seconds',{}))
            except Exception as exc:
                record.update(status='refused' if isinstance(exc,MemoryError) else 'failed',error_type=type(exc).__name__,error=str(exc),phase=phase[0])
                traceback.print_exc()
            finally:
                record.update(elapsed_seconds=time.perf_counter()-started,parent_cpu_seconds=time.process_time()-cpu_start,
                    final_rss=process.memory_info().rss)
                save(directory/'accounting.json',mb.report());save(directory/'last_plan.json',ledger.plan)
                save(directory/'result.json',record)
    print(json.dumps(record),flush=True)

def run(case):
    import psutil
    directory=HERE/'runs'/case['name'];directory.mkdir(parents=True,exist_ok=False)
    save(directory/'case.json',case);(HERE/'scratch').mkdir(exist_ok=True)
    env=dict(os.environ,PYTHONPATH=str(ROOT.parent),OPENBLAS_NUM_THREADS='4',MKL_NUM_THREADS='4',OMP_NUM_THREADS='4',
        TEMP=str(HERE/'scratch'),TMP=str(HERE/'scratch'),PYTHONIOENCODING='utf-8')
    started=time.monotonic();peak_rss=peak_private=0;minimum=psutil.virtual_memory().available;reason=None
    with (directory/'worker.log').open('w') as log,(directory/'samples.jsonl').open('w') as samples:
        child=subprocess.Popen([sys.executable,'-u',str(Path(__file__).resolve()),'--worker',str(directory/'case.json')],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        parent=psutil.Process(child.pid)
        while child.poll() is None:
            try:
                family=[parent]+parent.children(recursive=True);infos=[p.memory_info() for p in family]
                rss=sum(x.rss for x in infos);private=sum(getattr(x,'private',0) for x in infos);available=psutil.virtual_memory().available
                peak_rss=max(peak_rss,rss);peak_private=max(peak_private,private);minimum=min(minimum,available)
                samples.write(json.dumps(dict(seconds=time.monotonic()-started,rss=rss,private=private,available=available,processes=len(family),host_cpu=psutil.cpu_percent()))+'\n');samples.flush()
                if max(rss,private)>14*GIB:reason='14 GiB external process-tree guard'
                if available<2*GIB:reason='2 GiB external host reserve'
                if time.monotonic()-started>case.get('timeout',600):reason='time guard'
                if reason:
                    for process in reversed(family):
                        try:process.kill()
                        except psutil.NoSuchProcess:pass
                    child.wait();break
            except psutil.NoSuchProcess:pass
            time.sleep(.25)
    save(directory/'monitor.json',dict(returncode=child.returncode,stop_reason=reason,peak_tree_rss=peak_rss,
        peak_tree_private=peak_private,minimum_available=minimum,elapsed_seconds=time.monotonic()-started))
    if reason or not (directory/'result.json').exists():save(directory/'result.json',dict(status='stopped',reason=reason,returncode=child.returncode))
    record=json.loads((directory/'result.json').read_text());print(case['name'],json.dumps({k:record.get(k) for k in ('status','solve_seconds','error','phase')}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--worker');parser.add_argument('--plan');args=parser.parse_args()
    if args.worker:
        path=Path(args.worker);worker(json.loads(path.read_text()),path.parent)
    else:
        for case in json.loads(Path(args.plan).read_text()):run(case)
