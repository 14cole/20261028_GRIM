"""Supervised touched-memory ramp with actual system commit-limit observations."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
HOLD_GROWTH = '--hold-growth' in sys.argv
if HOLD_GROWTH:
    HERE=HERE/'pressure_hold'
    HERE.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT.parent))
GIB=1024**3
MIB=1024**2

def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')

def worker():
    import numpy as np
    import psutil
    from ghost_backend.execution import memory_budget as mb
    from ghost_backend.execution.memory import windows_system_commit,windows_available_commit_bytes
    from ghost_backend.execution.options import execution_scope
    from ghost_backend.twod import solver
    class Payload:bytes=0
    blocks=[];owner=Payload();process=psutil.Process()
    with (HERE/'pressure_events.jsonl').open('x') as stream:
        def emit(kind,**values):
            info=process.memory_info()
            stream.write(json.dumps(dict(kind=kind,system_commit=windows_system_commit(),
                available_commit_bytes=windows_available_commit_bytes(),available_ram_bytes=psutil.virtual_memory().available,
                rss_bytes=info.rss,private_bytes=getattr(info,'private',None),**values))+'\n');stream.flush()
        try:
            with execution_scope(dict(ram_budget_gib=32.)),mb.scope() as state:
                initial=state.initial_available*GIB;floor=max(GIB,.095*initial)
                initial_reservation=state.stable();started=time.monotonic();growth_deadline=None
                mb.register(owner)
                emit('start',initial_available_bytes=initial,initial_reservation_gib=initial_reservation,
                    initial_baseline_rss_bytes=state.baseline_rss,floor_bytes=floor)
                for fraction in (.70,.80,.85,.90):
                    desired=max(0,int(fraction*initial)-64*MIB)
                    while True:
                        target=min(desired,max(0,int(state.stable()*GIB)-64*MIB))
                        if owner.bytes>=target:
                            if HOLD_GROWTH and target<desired:
                                if growth_deadline is None:
                                    growth_deadline=time.monotonic()+10
                                    emit('growth_wait_start',owned_bytes=owner.bytes,stable_reservation_gib=state.stable())
                                if time.monotonic()<growth_deadline:
                                    time.sleep(.25)
                                    emit('growth_wait',owned_bytes=owner.bytes,stable_reservation_gib=state.stable())
                                    continue
                            break
                        count=min(64*MIB,target-owner.bytes)
                        if time.monotonic()-started>30:raise RuntimeError('30 second ramp bound')
                        if psutil.virtual_memory().available-count<floor:raise RuntimeError('physical reserve guard')
                        mb.admit_reload(count,workspace=0)
                        block=np.empty(count,dtype=np.uint8);block.fill(181)
                        blocks.append(block);owner.bytes+=count
                        # Record every GiB or the end of a target, not every page.
                        if owner.bytes%(GIB)<64*MIB or owner.bytes==target:
                            emit('allocation',owned_bytes=owner.bytes,stable_reservation_gib=state.stable())
                    state.require(owner.bytes/GIB,'Real touched payload')
                    emit('checkpoint',requested_fraction=fraction,actual_numeric_fraction=owner.bytes/initial,
                        target_reached=owner.bytes>=desired,stable_reservation_gib=state.stable(),
                        reserved_binding=state.last['reservation_binding_constraint'])
                save(HERE/'pressure_accounting.json',mb.report())
                emit('complete',seconds=time.monotonic()-started)
        except (MemoryError,RuntimeError) as exc:emit('stopped',reason=str(exc))
        finally:blocks.clear()

def monitor():
    import psutil
    for name in ('pressure_events.jsonl','pressure_monitor.json'):
        if (HERE/name).exists():raise RuntimeError('Refusing to overwrite '+name)
    initial=psutil.virtual_memory().available;floor=max(GIB,.095*initial)
    started=time.monotonic();peak=0;minimum=initial;reason=None
    with (HERE/'pressure_worker.log').open('x') as log:
        child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker']+(['--hold-growth'] if HOLD_GROWTH else []),cwd=ROOT,
            stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'))
        process=psutil.Process(child.pid)
        while child.poll() is None:
            try:
                peak=max(peak,process.memory_info().rss)
                available=psutil.virtual_memory().available;minimum=min(minimum,available)
                if available<floor:reason='external physical reserve guard'
                if time.monotonic()-started>45:reason='external 45 second limit'
                if reason:child.kill();child.wait();break
            except psutil.NoSuchProcess:pass
            time.sleep(.05)
    result=dict(returncode=child.returncode,stop_reason=reason,initial_available_bytes=initial,
        minimum_available_bytes=minimum,peak_rss_bytes=peak,seconds=time.monotonic()-started,
        scope='Touched numeric payload, not a complete numerical solve; no OS settings modified')
    save(HERE/'pressure_monitor.json',result);print(json.dumps(result,indent=2))

if __name__=='__main__':worker() if '--worker' in sys.argv else monitor()
