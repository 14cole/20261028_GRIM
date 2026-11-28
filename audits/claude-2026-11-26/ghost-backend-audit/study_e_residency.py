"""Physical-credit rule for a retained buffer: measured per-buffer residency, else nothing.

Compares it with a rule bounded by process RSS growth. Linux only; pages are released
with MADV_DONTNEED on zero-filled arrays (this host has no swap, so nothing can be paged out).

  GRIM_ROOT=<candidate tree> python study_e_residency.py out.json
"""
import ctypes, json, mmap, sys, time
import numpy as np
import harness  # noqa: F401  (puts the tree on sys.path)
from ghost_backend.execution import residency, memory_budget, dense_memory
import ghost_backend.twod.solver as solver

MIB = 2**20
SIZE = 256 * MIB
libc = ctypes.CDLL(None, use_errno=True)
libc.madvise.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]


def release(array):
    """Drop every whole page of the array; its contents read back as zero."""
    start = array.__array_interface__["data"][0]
    first = -(-start // mmap.PAGESIZE) * mmap.PAGESIZE
    length = (start + array.nbytes - first) // mmap.PAGESIZE * mmap.PAGESIZE
    assert libc.madvise(first, length, 4) == 0          # MADV_DONTNEED


def rss():
    return memory_budget.process_memory()[0]


rows = {}
with memory_budget.scope() as owner:
    base = rss()
    def rss_rule(nbytes):                               # the rule in Codex's revision
        return min(nbytes, max(0, rss() - owner.baseline_rss))

    def record(name, array, expect):
        measured = residency.resident_bytes(array)
        rows[name] = dict(array_mib=array.nbytes / MIB, measured_resident_mib=None if measured is None else measured / MIB,
                          credit_mib=dense_memory.bounded_reuse_hint(array) / MIB,
                          rss_growth_rule_mib=rss_rule(array.nbytes) / MIB,
                          process_rss_growth_mib=(rss() - owner.baseline_rss) / MIB, expected=expect)

    a = np.zeros(SIZE // 16, dtype=np.complex128); a[:] = 0          # every page written
    record("resident", a, "full")
    release(a)
    record("released", a, "zero")
    other = np.ones(SIZE // 16, dtype=np.complex128)                 # unrelated allocation of the same size
    record("released_then_unrelated_allocation", a, "zero")
    a[: a.size // 2] = 0                                             # half comes back
    record("half_restored", a, "half")
    del other
    b = np.empty(SIZE // 16, dtype=np.complex128)
    record("allocated_never_written", b, "zero")
    record("view_of_resident_buffer", np.ones(SIZE // 16, dtype=np.complex128)[1:], "zero (not an owned buffer)")
    record("fortran_ordered_matrix", np.ones((4096, 4096), dtype=np.complex128, order="F"), "full")
    c = np.ones(SIZE // 16, dtype=np.complex128)
    real = residency._posix
    residency._posix = lambda array: None                            # probe unavailable
    record("probe_unavailable", c, "zero")
    def broken(array):
        raise OSError("mincore failed")
    residency._posix = broken
    record("probe_raises", c, "zero")
    residency._posix = real
    owner.shared_process = True                                      # overlapping request scopes
    record("overlapping_requests", c, "zero")
    owner.shared_process = False

    # Effect on the admission limit under one controlled availability reading.
    real_available = solver._detect_available_gb
    reserve = 0.1 * owner.initial_available
    solver._detect_available_gb = lambda: reserve + 0.5              # 0.5 GiB of spendable headroom
    release(c)
    filler = np.ones(SIZE // 16, dtype=np.complex128)
    plain = solver._solve_memory_limit_gb()
    rows["limit_after_release_and_refill"] = dict(
        uncredited_limit_gib=plain,
        per_buffer_rule_limit_gib=solver._solve_memory_limit_gb(dense_memory.bounded_reuse_hint(c) / 2**30) if dense_memory.bounded_reuse_hint(c) else plain,
        rss_growth_rule_limit_gib=solver._solve_memory_limit_gb(rss_rule(c.nbytes) / 2**30),
        binding=owner.last["binding_constraint"])
    # Caps stay separate constraints: an explicit cap below the credited limit still binds.
    c[:] = 1
    import os
    os.environ["GHOST_MAX_SOLVE_GB"] = "0.3"
    rows["explicit_cap_with_full_credit"] = dict(
        credit_mib=dense_memory.bounded_reuse_hint(c) / MIB,
        limit_gib=solver._solve_memory_limit_gb(dense_memory.bounded_reuse_hint(c) / 2**30),
        binding=owner.last["binding_constraint"])
    del os.environ["GHOST_MAX_SOLVE_GB"]
    solver._detect_available_gb = real_available
    del filler

big = np.ones(2**31 // 16, dtype=np.complex128)
t = time.perf_counter(); residency.resident_bytes(big); rows["probe_seconds_per_gib"] = (time.perf_counter() - t) / 2
json.dump(rows, open(sys.argv[1], "w"), indent=1)
for k, v in rows.items():
    print(k, json.dumps(v))
