"""Short, supervised real-RAM accounting ramp; no solver or probe mocks.

This exercises touched allocation, ownership and incremental checks, not
numerical factorization at 90% RAM. All allocations die with the child process.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT.parent))
GIB = 1024**3
MIB = 1024**2
LABEL = sys.argv[sys.argv.index('--label')+1] if '--label' in sys.argv else 'physical_pressure'
if LABEL not in ('physical_pressure', 'physical_pressure_commit'):
    raise ValueError('Unknown evidence label')


def worker():
    import numpy as np
    import psutil
    from ghost_backend.execution import memory_budget as mb
    from ghost_backend.execution.options import execution_scope
    from ghost_backend.twod import solver  # Warm imports before baseline.
    class Payload:
        bytes = 0
    blocks = []
    owner = Payload()
    process = psutil.Process()
    stream = (HERE/(LABEL+'_events.jsonl')).open('x')
    def emit(kind, **values):
        info = process.memory_info()
        row = dict(kind=kind, rss_bytes=info.rss, private_bytes=getattr(info,'private',None),
            available_bytes=psutil.virtual_memory().available, **values)
        stream.write(json.dumps(row)+'\n'); stream.flush()
    try:
        with execution_scope(dict(ram_budget_gib=32.)), mb.scope() as ledger:
            budget = ledger.stable()*GIB
            available = ledger.initial_available*GIB
            floor = max(GIB, .095*available)
            started = time.monotonic()
            emit('start', initial_available_bytes=available, reservation_bytes=budget,
                initial_available_commit_bytes=None if ledger.initial_commit is None else ledger.initial_commit*GIB,
                reservation_constraints_gib=ledger.reservation_limits,
                baseline_rss_bytes=ledger.baseline_rss, floor_bytes=floor)
            mb.register(owner)
            for fraction in (.70, .80, .85, .90):
                # Leave room for real allocator metadata as well as numeric bytes.
                target = max(0, int(min(fraction*available, budget))-64*MIB)
                while owner.bytes < target:
                    size = min(64*MIB, target-owner.bytes)
                    if time.monotonic()-started > 30:
                        raise RuntimeError('30 second allocation ramp limit')
                    if psutil.virtual_memory().available-size < floor:
                        raise RuntimeError('live host reserve guard before allocation')
                    mb.admit_reload(size, workspace=0)
                    block = np.empty(size, dtype=np.uint8)
                    block.fill(173)  # Commit and touch every page; no lazy zeros.
                    blocks.append(block)
                    owner.bytes += size
                ledger.require(owner.bytes/GIB, 'Real touched payload')
                emit('checkpoint', requested_fraction=fraction, owned_bytes=owner.bytes,
                    credit_gib=ledger.last['credited_resident_gib'],
                    observed_payload_fraction=owner.bytes/available,
                    admitted=ledger.events[-1]['admitted'])
            # Must still reject an increment beyond the remaining stable cap.
            try:
                mb.admit_reload(int(budget-owner.bytes)+64*MIB, workspace=0)
            except MemoryError as exc:
                emit('expected_refusal', reason=str(exc))
            else:
                raise AssertionError('allocation beyond stable reservation admitted')
            emit('complete', seconds=time.monotonic()-started)
    except (MemoryError, RuntimeError) as exc:
        emit('stopped', reason=str(exc))
    finally:
        blocks.clear()
        stream.close()


def monitor():
    import psutil
    output = HERE/(LABEL+'_monitor.json')
    if output.exists() or (HERE/(LABEL+'_events.jsonl')).exists():
        raise RuntimeError('Refusing to overwrite an earlier physical pressure trial')
    started = time.monotonic()
    initial = psutil.virtual_memory().available
    floor = max(GIB, .095*initial)
    peak = 0; minimum = initial; reason = None
    with (HERE/(LABEL+'.log')).open('x') as log:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--worker', '--label', LABEL],
            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
            env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1'))
        process = psutil.Process(child.pid)
        while child.poll() is None:
            try:
                info = process.memory_info()
                peak = max(peak, info.rss)
                available = psutil.virtual_memory().available
                minimum = min(minimum, available)
                if available < floor: reason = 'external available-RAM guard'
                if time.monotonic()-started > 45: reason = 'external 45 second timeout'
                if reason:
                    child.kill(); child.wait(); break
            except psutil.NoSuchProcess:
                pass
            time.sleep(.05)
    result = dict(returncode=child.returncode, stop_reason=reason,
        peak_rss_bytes=peak, initial_available_bytes=initial, minimum_available_bytes=minimum,
        floor_bytes=floor, seconds=time.monotonic()-started,
        scope='Real touched payload accounting only; no numerical solver in this ramp')
    output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    worker() if '--worker' in sys.argv else monitor()
