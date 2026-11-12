"""One phase plan for CPU Dense admission and its execution choices.

Remote submissions keep the two-matrix forecast: the submitting host cannot
promise scratch space on a compute node. Each actual mesh replans locally.
Explicit memory storage, GPU, mixed precision and legacy HODLR keep their
existing conservative forecasts and fallback guards.
"""
import math
import os
from pathlib import Path
import shutil
import tempfile

GIB = 1024**3
MIB = 1024**2
MODEL = 'dense_phase_v1'


def current(dofs=None):
    from ghost_backend.execution.memory_budget import current as ledger
    owner = ledger()
    plan = owner.plan if owner is not None else None
    if plan and plan.get('model') == MODEL and (dofs is None or plan['system_dofs'] == dofs):
        return plan
    return None


def disk_backed_scratch(directory):
    """Do not buy a one-matrix RAM forecast with a RAM-backed temporary file."""
    try:
        if os.name == 'nt':
            import ctypes
            query = ctypes.windll.kernel32.GetDriveTypeW
            query.argtypes = [ctypes.c_wchar_p]
            query.restype = ctypes.c_uint
            return query(str(Path(directory).anchor)) not in (0, 1, 6)
        path = str(Path(directory).resolve())
        mounts = []
        for line in Path('/proc/self/mountinfo').read_text().splitlines():
            left, right = line.split(' - ', 1)
            mount = left.split()[4]
            for escaped, literal in ((r'\040', ' '), (r'\011', '\t'), (r'\012', '\n'), (r'\134', '\\')):
                mount = mount.replace(escaped, literal)
            if path == mount or path.startswith(mount.rstrip('/') + '/'):
                mounts.append((len(mount), right.split()[0]))
        return bool(mounts) and max(mounts)[1] not in ('tmpfs', 'ramfs', 'devtmpfs', 'hugetlbfs')
    except (OSError, ValueError, AttributeError):
        return False


def scratch_available(required):
    from ghost_backend.execution.options import temporary_directory
    try:
        directory = temporary_directory()
        if not disk_backed_scratch(directory):
            return False, 'scratch is RAM-backed or its backing filesystem is unknown'
        if shutil.disk_usage(directory).free < required + 64*MIB:
            return False, 'insufficient free scratch space'
        # A directory can exist but be unwritable. Recheck when creating the
        # real spool; disk availability is evidence, not a future reservation.
        with tempfile.TemporaryFile(prefix='ghost-scratch-check-', dir=directory):
            pass
        return True, None
    except (OSError, ValueError) as exc:
        return False, str(exc)


def forecast(d, count, batch, assembly, solve, extra, eligible, submission=False):
    from ghost_backend.execution.options import option
    from ghost_backend.execution.memory_budget import current as ledger
    from ghost_backend.twod.solver import _solve_memory_limit_gb
    from ghost_backend.linalg.residual_spool import ResidualSpool
    matrix = 16*d*d
    # Assembly and solve are phase peaks, not simultaneous. The process
    # baseline is explicit so live gates can credit it without crediting caches.
    overhead = int(extra) + 128*MIB
    storage = option('dense_residual_storage', 'auto')
    capacity = None if submission else int((ledger().stable() if ledger() is not None
                                           else _solve_memory_limit_gb())*GIB)
    scratch_ok, scratch_reason = False, None
    if eligible and not submission and storage != 'memory':
        scratch_ok, scratch_reason = scratch_available(matrix)
    row_count = min(d, max(ResidualSpool.min_block_rows, ResidualSpool.block_bytes//(16*d)))
    # One streaming buffer and one write conversion (not live together);
    # keep two buffers in the estimate as headroom for NumPy/BLAS products.
    spool_workspace = 2*16*d*row_count
    original_batch = batch

    def price(kind, width):
        execution = solve - 16*12*d*(original_batch-width)
        if kind == 'disk':
            execution = execution-matrix+spool_workspace
        phases = dict(assembly=assembly+overhead, factorization=execution+overhead,
                      solve=execution+overhead)
        return phases, max(phases.values())

    chosen = 'disk' if eligible and scratch_ok and storage == 'disk' else 'memory'
    phases, peak = price(chosen, batch)
    initial_peak = peak
    if eligible and capacity is not None and peak > capacity and storage != 'memory' and scratch_ok:
        chosen = 'disk'
        phases, peak = price(chosen, batch)
        # Narrow batches only for a constrained disk plan. Never spend their
        # saving on an optional retained TE/TM partner matrix.
        while peak > capacity and batch > 1:
            batch = max(1, min(64, batch//2))
            phases, peak = price(chosen, batch)
    constrained = capacity is not None and initial_peak > capacity
    return dict(model=MODEL, system_dofs=d, matrix_bytes=matrix,
        peak_bytes=int(math.ceil(peak)), phase_bytes={k:int(v) for k,v in phases.items()},
        process_baseline_bytes=128*MIB, process_geometry_bytes=overhead,
        angle_batch_size=batch, requested_angle_batch_size=original_batch,
        residual_storage=chosen, residual_storage_requested=storage,
        residual_spool_workspace_bytes=spool_workspace if chosen == 'disk' else 0,
        temporary_disk_bytes=matrix if chosen == 'disk' else 0,
        scratch_checked=eligible and not submission and storage != 'memory',
        scratch_available=scratch_ok, scratch_failure=scratch_reason,
        submission_planning=bool(submission), capacity_bytes=capacity,
        memory_recovery=constrained, assembly_tile=128 if constrained and eligible else 0,
        paired_assembly=False, partner_matrix_bytes=0,
        allow_optional_partner=not constrained and chosen == 'memory',
        forecast_is_hard_limit=False)


def pair(dofs, allowed):
    """Record the optional partner in the same plan used by execution."""
    plan = current(dofs)
    if plan is None:
        return allowed
    allowed = bool(allowed and plan['allow_optional_partner'])
    previous = plan['partner_matrix_bytes']
    partner = plan['matrix_bytes'] if allowed else 0
    plan['phase_bytes'] = {k:v-previous+partner for k,v in plan['phase_bytes'].items()}
    plan.update(paired_assembly=allowed, partner_matrix_bytes=partner,
                peak_bytes=max(plan['phase_bytes'].values()))
    return allowed


def factor_workspace(dofs):
    """Bound the next RHS/residual work when a live factor allocation is admitted."""
    plan = current(dofs)
    if plan is None:
        return 0
    return 64*MIB + 16*12*dofs*plan['angle_batch_size'] + plan['residual_spool_workspace_bytes']


def admit_spool(matrix):
    """Recheck current RAM before overwriting the only in-memory original."""
    plan = current(len(matrix))
    if plan is None:
        return
    from ghost_backend.twod.solver import _process_rss_bytes, _solve_memory_limit_gb
    from ghost_backend.compressed.worker_pool import retained_bytes
    resident = max(matrix.nbytes, _process_rss_bytes()) + retained_bytes()
    available = _solve_memory_limit_gb(resident/GIB)*GIB-resident
    from ghost_backend.linalg.residual_spool import ResidualSpool
    n = len(matrix)
    rows = min(n, max(ResidualSpool.min_block_rows, ResidualSpool.block_bytes//(16*n)))
    needed = factor_workspace(n) + max(0, 32*n*rows-plan['residual_spool_workspace_bytes'])
    if available < needed:
        raise MemoryError('Dense disk residual workspace no longer fits the remaining solve RAM budget.')


def assembly_tile_setting(default=0, planned=True):
    """Effective tile override, also part of retained-operator cache identities."""
    from ghost_backend.execution.options import option
    explicit = int(option('assembly_tile', default))
    plan = current() if planned else None
    return explicit if explicit > 0 else int(plan['assembly_tile']) if plan else 0
