"""Serial isolated timing/profile studies; source selection is explicit and recorded."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GIB = 1024**3

def save(path, value): path.write_text(json.dumps(value,indent=2,default=str)+'\n')

def worker(args):
    backend = Path(args.backend).resolve()
    sys.path.insert(0,str(backend.parent))
    import numpy as np
    import psutil
    import threading
    import weakref
    from unittest.mock import patch
    from ghost_backend.twod import solver
    from ghost_backend.compressed import worker_pool
    from ghost_backend.execution import memory_budget, metrics
    assert Path(solver.__file__).resolve().is_relative_to(backend)
    directory = HERE/'runs'/args.name
    case = 'dielectric15' if args.case=='dielectric15' else 'narrow15' if args.case=='narrow15' else 'inlet15'
    prior = HERE.parent/'memory_followups_20261029'/('live_'+case)
    request = json.loads((prior/'request.json').read_text())
    options = request['options']; options.update(assembly_threads=args.threads,blas_threads=4,
        ram_budget_gib=args.cap,temporary_directory=str(HERE/'scratch'))
    save(directory/'request.json',dict(request=request['request'],options=options,backend=str(backend),
        release_idle_before_hierarchical=args.release_idle))
    stream = (directory/'samples.jsonl').open('w')
    process = psutil.Process(); stop = threading.Event(); pools = weakref.WeakSet()
    phase = ['prepare']; cpu_by_pid = {}; samples = [0,0.]; peaks = {}; lifecycle = []
    instrument = dict(limit_calls=0,limit_seconds=0.,worker_snapshot_calls=0,worker_snapshot_seconds=0.)
    original_prepare, original_close = worker_pool.WorkerPool.prepare, worker_pool.WorkerPool.close
    original_snapshot, original_limit = worker_pool.WorkerPool.memory_snapshot, memory_budget.MemoryBudget.limit
    original_estimate = solver._estimate_memory_gb
    def prepare(self,payload):
        pools.add(self)
        result = original_prepare(self,payload)
        lifecycle.append(dict(event='prepare',workers=self.workers,generation=self.generation,payload_bytes=self.payload_bytes))
        return result
    def close(self):
        lifecycle.append(dict(event='close',workers=self.workers,generation=self.generation,payload_bytes=self.payload_bytes))
        return original_close(self)
    def snapshot(self):
        started=time.perf_counter()
        try:return original_snapshot(self)
        finally:
            instrument['worker_snapshot_calls']+=1
            instrument['worker_snapshot_seconds']+=time.perf_counter()-started
    def limit(self,*a,**k):
        started=time.perf_counter()
        try:return original_limit(self,*a,**k)
        finally:
            instrument['limit_calls']+=1
            instrument['limit_seconds']+=time.perf_counter()-started
    def estimate(*a,**k):
        resources=k.get('dense_resources') or {}
        if args.release_idle and k.get('activate_memory_plan') and resources.get('hmatrix_storage'):
            released=worker_pool.release_idle()
            if released:lifecycle.append(dict(event='release_before_hierarchical',bytes=released))
        return original_estimate(*a,**k)
    started=time.perf_counter()
    def sample():
        begin=time.perf_counter()
        try:
            children=process.children(recursive=True)
            infos=[]
            for child in children:
                info=child.memory_full_info(); times=child.cpu_times()
                cpu_by_pid[child.pid]=max(cpu_by_pid.get(child.pid,0),times.user+times.system)
                infos.append(info)
            info=process.memory_info(); times=process.cpu_times()
            cpu_by_pid[process.pid]=times.user+times.system
            live=[p for p in list(pools) if not p.closed]
            row=dict(seconds=time.perf_counter()-started,stage=phase[0],
                busy=any(p.busy for p in live),workers=len(infos),
                worker_rss=sum(i.rss for i in infos),worker_uss=sum(getattr(i,'uss',0) for i in infos),
                worker_private=sum(getattr(i,'private',0) for i in infos),
                worker_peak_private_sum=sum(getattr(i,'peak_pagefile',0) for i in infos),
                parent_rss=info.rss,parent_private=getattr(info,'private',0),
                retained_allowance=sum(p.reserved_bytes for p in live),
                payload_bytes=sum(p.payload_bytes for p in live),
                available=psutil.virtual_memory().available,host_cpu_percent=psutil.cpu_percent(),
                host_cpu_frequency_mhz=getattr(psutil.cpu_freq(),'current',None))
            stream.write(json.dumps(row)+'\n'); stream.flush()
            for key in ('worker_rss','worker_uss','worker_private','worker_peak_private_sum','retained_allowance','payload_bytes'):
                peaks[key]=max(peaks.get(key,0),row[key])
            samples[0]+=1
        except (psutil.NoSuchProcess, psutil.AccessDenied):pass
        finally:samples[1]+=time.perf_counter()-begin
    def poll():
        while not stop.wait(.25):sample()
    sampler=threading.Thread(target=poll,daemon=True)
    try:
        with patch.object(worker_pool.WorkerPool,'prepare',prepare),patch.object(worker_pool.WorkerPool,'close',close), \
             patch.object(worker_pool.WorkerPool,'memory_snapshot',snapshot),patch.object(memory_budget.MemoryBudget,'limit',limit), \
             patch.object(solver,'_estimate_memory_gb',estimate),metrics.progress_listener(lambda e:phase.__setitem__(0,e['stage_key'])):
            sampler.start(); solve_start=time.perf_counter(); cpu_start=time.process_time()
            result=solver.solve_monostatic_rcs_2d_certified(**request['request'],execution_options=options)
            wall=time.perf_counter()-solve_start; parent_cpu=time.process_time()-cpu_start
        metadata=result['metadata']; save(directory/'metadata.json',metadata)
        actual={pol:np.asarray([complex(r['rcs_amp_real'],r['rcs_amp_imag']) for r in rows])
                for pol,rows in result['co_solved_samples'].items()}
        reference_name={'inlet15':'solver_studies_20261029/runs/metal15_r1_compressed',
            'narrow15':'solver_studies_20261029/runs/narrow15_r1_compressed',
            'dielectric15':'automatic_selection_20261029/runs/dielectric15_r0_compressed'}[case]
        with np.load(HERE.parent/reference_name/'fields.npz') as reference:
            errors={pol:float(np.max(abs(values-reference[pol]))) for pol,values in actual.items()}
        assert metadata['quality_gate']['passed'] and metadata['mesh_convergence_certified'] and max(errors.values())<1e-8
        save(directory/'result.json',dict(status='passed',wall_seconds=wall,parent_cpu_seconds=parent_cpu,
            sampled_family_cpu_seconds=sum(cpu_by_pid.values()),field_max_absolute_errors=errors,
            certified=True,instrumentation=instrument,sampler_calls=samples[0],sampler_seconds=samples[1],
            worker_peaks=peaks,lifecycle=lifecycle))
    except Exception as exc:
        import traceback; traceback.print_exc()
        save(directory/'result.json',dict(status='failed',error=repr(exc),instrumentation=instrument))
        raise
    finally:
        stop.set();sampler.join(timeout=5);stream.close()

def run(args):
    import psutil
    directory=HERE/'runs'/args.name;directory.mkdir(parents=True)
    (HERE/'scratch').mkdir(exist_ok=True)
    backend=Path(args.backend).resolve()
    env=dict(os.environ,OPENBLAS_NUM_THREADS='4',MKL_NUM_THREADS='4',OMP_NUM_THREADS='4',
        TEMP=str(HERE/'scratch'),TMP=str(HERE/'scratch'),PYTHONIOENCODING='utf-8',PYTHONPATH=str(backend.parent))
    command=[sys.executable,'-u',str(Path(__file__).resolve()),'--worker','--name',args.name,
        '--backend',str(backend),'--threads',str(args.threads),'--cap',str(args.cap),'--case',args.case]
    if args.release_idle:command.append('--release-idle')
    started=time.monotonic();reason=None;rss_peak=private_peak=0
    with (directory/'worker.log').open('w') as log:
        child=subprocess.Popen(command,cwd=backend.parent,env=env,stdout=log,stderr=subprocess.STDOUT)
        process=psutil.Process(child.pid)
        while child.poll() is None:
            try:
                family=[process]+process.children(recursive=True); infos=[p.memory_info() for p in family]
                rss=sum(i.rss for i in infos);private=sum(getattr(i,'private',0) for i in infos)
                rss_peak=max(rss_peak,rss);private_peak=max(private_peak,private)
                if max(rss,private)>8*GIB:reason='8 GiB process-tree guard'
                if psutil.virtual_memory().available<2*GIB:reason='2 GiB available RAM guard'
                if time.monotonic()-started>600:reason='600 second guard'
                if reason:
                    for p in reversed(family):
                        try:p.kill()
                        except psutil.NoSuchProcess:pass
                    child.wait();break
            except psutil.NoSuchProcess:pass
            time.sleep(.25)
    save(directory/'monitor.json',dict(returncode=child.returncode,stop_reason=reason,
        peak_tree_rss=rss_peak,peak_tree_private=private_peak,elapsed_seconds=time.monotonic()-started))
    if child.returncode or reason:raise RuntimeError('Trial failed: '+args.name)
    print(args.name,(directory/'result.json').read_text(),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--name',required=True);parser.add_argument('--backend',required=True)
    parser.add_argument('--case',default='inlet15',choices=['inlet15','narrow15','dielectric15'])
    parser.add_argument('--threads',type=int,default=4);parser.add_argument('--cap',type=float,default=6.)
    parser.add_argument('--worker',action='store_true');parser.add_argument('--release-idle',action='store_true')
    args=parser.parse_args();worker(args) if args.worker else run(args)
