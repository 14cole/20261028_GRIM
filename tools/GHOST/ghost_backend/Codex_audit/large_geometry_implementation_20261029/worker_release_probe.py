"""Measure release/restart of real numerical tile workers in an owned scope."""
import json
import os
from pathlib import Path
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT.parent),str(ROOT/'tests')]
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
import psutil
from test_worker_moment_cache import NearOracle, payload
from ghost_backend.compressed import worker_pool, tile_processes
from ghost_backend.twod.preparation import preparation_scope
from ghost_backend.execution.runtime import single_thread_worker_environment


if __name__=='__main__':
    oracle=NearOracle(3)
    reference=oracle.get_with_error(np.arange(4),np.arange(4))[0]
    with preparation_scope(), tile_processes._without_main_module(), single_thread_worker_environment():
        pool=worker_pool.acquire(2)
        path=pool.prepare(payload(oracle))
        futures=[pool.executor.submit(worker_pool.run_tile,path,(0,0,[0])) for _ in range(4)]
        for future in futures:
            np.testing.assert_array_equal(future.result(timeout=30)[0][0][0],reference)
        children=list(pool.executor._processes.values())
        rss=sum(psutil.Process(p.pid).memory_info().rss for p in children)
        started=time.perf_counter()
        reservation=worker_pool.release_idle()
        release_seconds=time.perf_counter()-started
        assert all(not p.is_alive() for p in children)
        assert not Path(path).exists()
        assert worker_pool.retained_bytes()==0
        started=time.perf_counter()
        replacement=worker_pool.acquire(2)
        result=replacement.executor.submit(worker_pool.run_tile,
            replacement.prepare(payload(oracle)),(0,0,[0])).result(timeout=30)
        np.testing.assert_array_equal(result[0][0][0],reference)
        restart_seconds=time.perf_counter()-started
        assert replacement is not pool
    record=dict(status='passed',workers=len(children),released_child_rss_bytes=rss,
        released_forecast_allowance_bytes=reservation,release_seconds=release_seconds,
        restart_and_one_tile_seconds=restart_seconds,
        fields='near-quadrature tile coefficients exactly equal before and after restart',
        scope='isolated pool lifecycle; does not imply all solve RSS or the full reservation was resident')
    (HERE/'worker_release.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record))
