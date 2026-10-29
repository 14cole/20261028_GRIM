"""Instrument one real default-compressed solve without altering budgets or gates."""
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
sys.path[:0] = [str(ROOT.parent), str(ROOT/'tests')]
GIB = 1024**3


def save(path, value):
    path.write_text(json.dumps(value, indent=2, default=str)+'\n')


def worker():
    import numpy as np
    import psutil
    from unittest.mock import patch
    from ghost_backend.compressed import runtime
    from ghost_backend.compressed.factor import CompressedFactor
    from ghost_backend.twod import solver
    from ghost_backend.execution.metrics import progress_listener
    spec=importlib.util.spec_from_file_location('prior_study', HERE.parent/'solver_studies_20261029/study.py')
    prior=importlib.util.module_from_spec(spec); spec.loader.exec_module(prior)
    directory=HERE/'live_inlet15'
    started=time.perf_counter()
    process=psutil.Process()
    stream=(directory/'events.jsonl').open('w')
    def emit(kind, **values):
        info=process.memory_info()
        stream.write(json.dumps(dict(kind=kind,seconds=time.perf_counter()-started,
            rss_bytes=info.rss,private_commit_bytes=getattr(info,'private',None),
            available_bytes=psutil.virtual_memory().available,**values),default=str)+'\n')
        stream.flush()
    original_limit=solver._solve_memory_limit_gb
    original_storage=runtime.automatic_storage_bytes
    original_init=CompressedFactor.__init__
    def limit(*args,**kwargs):
        result=original_limit(*args,**kwargs)
        frame=sys._getframe(1)
        emit('solve_limit',limit_gib=result,resident_credit_gib=args[0] if args else kwargs.get('resident_gb',0),
             caller=frame.f_code.co_filename,line=frame.f_lineno)
        return result
    def storage():
        result=original_storage()
        emit('automatic_storage',storage_bytes=result)
        return result
    def factor_init(self,operator,*args,**kwargs):
        emit('factor_start',operator_bytes=operator.bytes,
             partner_bytes=getattr(operator,'reserved_partner_bytes',0))
        original_init(self,operator,*args,**kwargs)
        emit('factor_finish',inverse_budget_bytes=self.budget,
             actual_inverse_bytes=self.factor.bytes,operator_bytes=operator.bytes)
    options=dict(mesh_strategy='adaptive',basis_order=1,mesh_grading=True,
        assembly_threads=4,blas_threads=4,compressed_storage_mib=0,angle_batch_size=256,
        temporary_directory=str(HERE/'scratch'))
    request=dict(geometry_snapshot=prior.geometry('inlet'), frequencies_ghz=[15.],
        elevations_deg=list(range(361)),geometry_units='inches',max_panels=100000)
    save(directory/'request.json',dict(request=request,options=options,
        note='No explicit backend or RAM cap; current public compressed default; real availability.'))
    try:
        with patch.object(solver,'_solve_memory_limit_gb',limit), \
             patch.object(runtime,'automatic_storage_bytes',storage), \
             patch.object(CompressedFactor,'__init__',factor_init), \
             progress_listener(lambda e:emit('stage',event=e)):
            result=solver.solve_monostatic_rcs_2d_certified(**request,execution_options=options)
        metadata=result['metadata']
        save(directory/'metadata.json',metadata)
        actual={p:np.array([complex(r['rcs_amp_real'],r['rcs_amp_imag']) for r in rows])
                for p,rows in result['co_solved_samples'].items()}
        reference=HERE.parent/'solver_studies_20261029/runs/metal15_r1_compressed/fields.npz'
        errors={}
        with np.load(reference) as prior_fields:
            for pol,value in actual.items():
                errors[pol]=float(np.max(abs(value-prior_fields[pol]))/max(1.,np.max(abs(prior_fields[pol]))))
        assert metadata['quality_gate']['passed'] and metadata['mesh_convergence_certified']
        assert max(errors.values()) < 1e-8
        save(directory/'result.json',dict(status='passed',seconds=time.perf_counter()-started,
            quality_passed=True,mesh_certified=True,relative_max_field_differences=errors,
            reference=str(reference.relative_to(ROOT)),reference_comparison='max abs field difference / max(1, max abs reference)'))
    except Exception as exc:
        traceback.print_exc()
        save(directory/'result.json',dict(status='rejected',error_type=type(exc).__name__,error=str(exc)))
    finally:
        stream.close()


def run():
    import psutil
    directory=HERE/'live_inlet15'; directory.mkdir()  # refuse overwrite
    scratch=HERE/'scratch';scratch.mkdir(exist_ok=True)
    env=dict(os.environ,OPENBLAS_NUM_THREADS='4',MKL_NUM_THREADS='4',OMP_NUM_THREADS='4',
             TEMP=str(scratch),TMP=str(scratch),PYTHONIOENCODING='utf-8')
    start=time.monotonic();rss_peak=private_peak=0;reason=None
    available_start=minimum_available=psutil.virtual_memory().available
    with (directory/'worker.log').open('w') as log:
        process=subprocess.Popen([sys.executable,'-u',str(Path(__file__).resolve()),'--worker'],
            cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        parent=psutil.Process(process.pid)
        while process.poll() is None:
            try:
                family=[parent]+parent.children(recursive=True)
                memory=[p.memory_info() for p in family]
                rss=sum(m.rss for m in memory);private=sum(getattr(m,'private',0) for m in memory)
                rss_peak=max(rss_peak,rss);private_peak=max(private_peak,private)
                available=psutil.virtual_memory().available;minimum_available=min(minimum_available,available)
                if max(rss,private)>6*GIB:reason='6 GiB tree RSS/private guard'
                if available<2*GIB:reason='2 GiB available-memory floor'
                if time.monotonic()-start>600:reason='600 second limit'
                if reason:
                    for p in reversed(family):
                        try:p.kill()
                        except psutil.NoSuchProcess:pass
                    process.wait();break
            except psutil.NoSuchProcess:
                pass
            time.sleep(.1)
    save(directory/'monitor.json',dict(returncode=process.returncode,stop_reason=reason,
        peak_rss_bytes=rss_peak,peak_private_bytes=private_peak,host_available_start_bytes=available_start,
        host_available_minimum_bytes=minimum_available,elapsed_seconds=time.monotonic()-start,
        sampling_seconds=.1,scope='isolated process tree, RSS may double-count shared pages; private is Windows commit'))
    print((directory/'monitor.json').read_text())
    if (directory/'result.json').exists():print((directory/'result.json').read_text())


if __name__=='__main__':
    if '--worker' in sys.argv:worker()
    else:run()
