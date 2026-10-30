"""Run-owned spawned tile workers, with bounded retained residency."""
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
from pathlib import Path
import tempfile
import time
import threading

_GENERATION = None
_POOL_LOCK = threading.RLock()


def run_tile(path, task):
    global _GENERATION
    prepared=0.
    from ghost_backend.compressed import tile_processes as tiles
    if _GENERATION != path:
        started=time.perf_counter()
        # Drop mesh/oracle/CPU tables, but retain the separately bounded near
        # moments. Their keys include geometry, wavenumber, direction and rule;
        # compatible P2/P3 generations can therefore reuse the same integrals.
        tiles._WORKER = None
        import gc
        gc.collect()
        tiles._initialize(Path(path).read_bytes())
        _GENERATION = path
        prepared=time.perf_counter()-started
    result,counters=tiles._tile(task)
    if counters.component_seconds is not None:
        counters.component_seconds['prepare']=prepared
    return result,counters


class WorkerPool:
    def __init__(self, workers):
        self.workers = workers
        self.executor = ProcessPoolExecutor(workers, mp_context=mp.get_context('spawn'))
        self.directory = tempfile.TemporaryDirectory(prefix='ghost-tile-workers-')
        self.generation = 0
        self.payload_bytes = 0
        self.path = None
        self.closed = False
        self.busy = False
        from ghost_backend.execution.memory_budget import register
        register(self,'workers')

    def memory_snapshot(self):
        """Owned workers only; USS credit avoids shared-page double counting.

        Current residency is evidence, not a substitute for remaining buffer
        and cache growth in the forecast. Missing samples receive no credit.
        """
        return self._memory_snapshot(incremental=False)

    def incremental_memory_snapshot(self):
        """Live RSS/private charge for extra allocations, never residency credit.

        Windows memory_info includes private commit without the costly working
        set walk used for USS. RSS conservatively includes shared pages. Other
        platforms keep the full probe when private commit is unavailable.
        """
        return self._memory_snapshot(incremental=True)

    def _memory_snapshot(self, incremental):
        result=dict(rss_bytes=0,private_bytes=0,unique_resident_bytes=0,
                    residency_credit_eligible=not incremental,
                    processes=0,complete=True,reservation_bytes=self.reserved_bytes if not self.closed else 0)
        if self.closed:
            return result
        try:
            import psutil
            for process in list((getattr(self.executor,'_processes',None) or {}).values()):
                worker=psutil.Process(process.pid)
                info=worker.memory_info() if incremental else worker.memory_full_info()
                if incremental and not hasattr(info, 'private'):
                    info=worker.memory_full_info()
                result['processes']+=1
                result['rss_bytes']+=int(info.rss)
                result['private_bytes']+=int(getattr(info,'private',0))
                if not incremental:
                    result['unique_resident_bytes']+=int(getattr(info,'uss',0))
        except Exception:
            result.update(complete=False,unique_resident_bytes=0,private_bytes=0)
        return result

    def construction_observation_key(self):
        """Cheap identity for an idle team; active work must be sampled live.

        Every prepared traversal changes generation. Worker replacement,
        closure and payload changes also invalidate a previous observation.
        This method never probes an OS process or grants residency credit.
        """
        if self.busy:
            return None
        processes = getattr(self.executor, '_processes', None) or {}
        try:
            pids = [process.pid for process in list(processes.values())]
            if any(pid is None for pid in pids):
                return None
            return (self.closed, self.generation, self.workers, self.payload_bytes, tuple(sorted(pids)))
        except (RuntimeError, AttributeError, TypeError):
            return None

    def prepare(self, payload):
        if self.closed:
            raise RuntimeError('Cannot prepare a closed tile-worker pool.')
        if self.path is not None:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
        self.generation += 1
        self.path = Path(self.directory.name) / ('oracle-{}.bin'.format(self.generation))
        self.path.write_bytes(payload)
        self.payload_bytes = len(payload)
        return str(self.path)

    @property
    def reserved_bytes(self):
        from ghost_backend.compressed.tile_processes import WORKER_BYTES
        return self.workers * (WORKER_BYTES + 2*self.payload_bytes)

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            for process in list((getattr(self.executor, '_processes', None) or {}).values()):
                if process.is_alive():
                    process.terminate()
            try:
                self.executor.shutdown(wait=True, cancel_futures=True)
            except TypeError:  # Python versions before cancel_futures was added.
                self.executor.shutdown(wait=True)
        finally:
            self.directory.cleanup()


def acquire(workers, lease=False):
    """Atomically acquire exclusive traversal ownership before preparation."""
    with _POOL_LOCK:
        return _acquire(workers, lease)


def _acquire(workers, lease):
    from ghost_backend.twod.preparation import run_resources
    resources = run_resources()
    if resources is None:
        return None
    previous = resources.get('compressed_tile_workers')
    if previous is not None and previous.busy:
        raise RuntimeError('The run already has an active tile-worker traversal.')
    if previous is not None and (previous.closed or previous.workers != workers):
        previous.close()
        previous = None
    if previous is None:
        previous = WorkerPool(workers)
        resources['compressed_tile_workers'] = previous
    if lease:
        previous.busy = True
    return previous


def release_lease(pool, failed=False):
    """Release ownership even when preparation or traversal was interrupted."""
    with _POOL_LOCK:
        try:
            if failed:
                pool.close()
        finally:
            pool.busy = False


def retained_bytes():
    with _POOL_LOCK:
        return _retained_bytes()


def _retained_bytes():
    from ghost_backend.twod.preparation import run_resources
    resources = run_resources()
    pool = resources.get('compressed_tile_workers') if resources else None
    return pool.reserved_bytes if pool is not None and not pool.closed else 0


def release_idle():
    """Release a run's idle tile team before refusing subsequent work for RAM."""
    with _POOL_LOCK:
        return _release_idle()


def _release_idle():
    from ghost_backend.twod.preparation import run_resources
    resources = run_resources()
    pool = resources.get('compressed_tile_workers') if resources else None
    if pool is None or pool.closed or pool.busy:
        return 0
    released = pool.reserved_bytes
    pool.close()
    resources.pop('compressed_tile_workers', None)
    return released


def forecast_bytes(dofs, threads, groups=None):
    """Price workers in every phase, including when idle during factorization."""
    from ghost_backend.compressed.tile_processes import MIN_TILES, MAX_WORKERS, WORKER_BYTES
    from ghost_backend.execution.options import environment_value
    import math
    if groups is None:
        groups = 2**int(math.ceil(math.log(max(1., dofs/512.), 2)))
    if mp.current_process().daemon or groups**2 < MIN_TILES:
        return retained_bytes()
    configured = environment_value('GHOST_TILE_PROCESSES', '').strip()
    count = min(MAX_WORKERS, int(threads), int(configured) if configured else int(threads))
    anticipated = max(0, count)*WORKER_BYTES if count >= 2 else 0
    return max(retained_bytes(), anticipated)
