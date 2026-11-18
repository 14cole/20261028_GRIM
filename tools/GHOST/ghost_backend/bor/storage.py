"""Shared BoR operator-storage estimates for previews and solve admission."""
from collections import namedtuple
import numpy as np
from ghost_backend.bor.kernels import FAR_GAUSS_ORDER, FFT_BUILD_BUDGET, n_xi_for_pairs
from ghost_backend.bor.options import compressed_requested
_COMPLEX128_BYTES = np.dtype(np.complex128).itemsize


def bor_impedance_map_bytes(nodes: 'int') -> 'float':
    """Bound on the sparse ``2N x 2N`` J-to-M impedance map of a bare IBC piece
    with ``nodes`` nodes: 2N complex nonzeros plus CSR indices, priced with
    64-bit indices so a preview never falls below the gate's exact size."""
    count = 2 * int(nodes)
    return float(count * (16 + 8) + (count + 1) * 8)

def estimate_bor_table_gb(n_elems: 'int', m_max: 'int', formulation: 'str' = "cfie",
                          has_ibc: 'bool' = False, gauss_order: 'int' = FAR_GAUSS_ORDER,
                          single_tables: 'bool' = False) -> 'float':
    """Estimate persistent far-table storage for all modal FFT tables in GB."""

    P = float(gauss_order * n_elems)
    per = 8.0 if single_tables else 16.0
    total = P * P * (m_max + 2) * per
    if formulation in ("cfie", "mfie"):
        total += 4.0 * P * P * (m_max + 1) * per
    if has_ibc:
        total += 4.0 * P * P * (m_max + 1) * per
    return total / 1e9

def estimate_bor_cross_table_gb(
    n_test_elements: 'int', n_source_elements: 'int', m_max: 'int',
    test_gauss_order: 'int' = FAR_GAUSS_ORDER, source_gauss_order: 'int' = FAR_GAUSS_ORDER,
    single_tables: 'bool' = False, has_rotated_pv: 'bool' = True,
) -> 'float':
    """Persistent far tables for one directed rectangular T/P mapping."""

    test_points = float(int(test_gauss_order) * int(n_test_elements))
    source_points = float(int(source_gauss_order) * int(n_source_elements))
    modes = int(m_max)
    if test_points <= 0.0 or source_points <= 0.0 or modes < 0:
        raise ValueError("Cross-table estimate dimensions are invalid.")
    item_bytes = 8.0 if single_tables else 16.0
    modal_values = (modes + 2) + int(has_rotated_pv) * 4.0 * (modes + 1)
    return test_points * source_points * modal_values * item_bytes / 1.0e9

BOR_RETAINED_STORAGE_FACTOR = 1.10

def conductor_operator_kinds(formulation: 'str', has_impedance: 'bool'):
    """``(efie, mfie, ibc)``: the operator families a conductor solve prepares.

    One description for ``solve_bor``, its admission gate and the dispatch
    previews. Every enabled family retains its own far tables and its own
    same-surface near contractions, so a CFIE with a nonzero impedance holds
    three of each. The previews assumed two per surface and could fall below
    the gate they predict on bodies with many geometrically close panels.
    """
    efie, mfie = formulation in ("efie", "cfie"), formulation in ("cfie", "mfie")
    return efie, mfie, bool(has_impedance) and efie

def bor_near_cache_bytes(pair_count, node_count, kinds, modes) -> 'float':
    """Retained same-surface near contractions of one medium side.

    ``kinds`` operator families, each holding four component blocks of
    ``4*pair_count`` basis pairs per retained mode and its routing indices.
    The run-time gate and the snapshot preview both price them here.
    """
    index_bytes = np.dtype(np.intp).itemsize
    values = int(kinds) * 4.0 * (int(modes) + 1) * (4 * int(pair_count)) * _COMPLEX128_BYTES
    return values + int(kinds) * (4.0 * (4 * int(pair_count)) + int(node_count) + 1) * index_bytes

def bor_cross_near_cache_bytes(pair_count, modes, has_rotated_pv=True) -> 'float':
    """Retained near contractions of one directed cross-surface operator."""
    return int(pair_count) * (1 + int(has_rotated_pv)) * 4 * (int(modes) + 1) * 4 * _COMPLEX128_BYTES

# What one medium side of a surface, and one directed cross-surface operator,
# contribute to operator storage.  The run-time gate fills these from the
# constructed solvers; the dispatch previews fill them from mesh counts and
# geometric near-pair counts.  ``fft_samples`` is ``(scalar, bracket)`` angular
# sample counts, or ``None`` where only the bound ``FFT_BUILD_BUDGET`` is known.
BorSurfaceStorage = namedtuple(
    'BorSurfaceStorage', 'points nodes table_bytes near_pairs efie mfie ibc fft_samples')

BorCrossStorage = namedtuple(
    'BorCrossStorage', 'points_p points_q table_bytes near_pairs near_max_order fft_samples has_rotated_pv',
    defaults=(True,))

def bor_operator_storage_bytes(modes, surfaces, crosses=(), constraint_dofs=0,
                               streaming=False, compressed=False):
    """The one BoR operator-storage model, in bytes, by component.

    ``tables`` are the retained far tables (absent when streaming, whose
    planner prices far blocks itself). ``basis`` is retained as a zero-valued
    reporting field: production contracts local bases without dense matrices.
    ``near`` the same- and cross-surface near contractions, ``projection`` the
    junction projection matrices, ``fft_workspace`` and ``near_workspace`` the
    largest build scratch of each kind.  A gate needs
    ``BOR_RETAINED_STORAGE_FACTOR * (tables + basis + near + projection) +
    max(fft_workspace, near_workspace)``; the previews add the two workspaces
    instead, so they never fall below the gate they predict.  The function is
    monotone in every record field: records that bound the solvers' own bound
    the result.
    """

    from ghost_backend.bor import kernels
    modes = int(modes)
    signed_modes = 2 * modes + 1
    budget = float(FFT_BUILD_BUDGET)
    tables = basis = near = fft_workspace = near_workspace = 0.0

    def fft_bytes(pair_points, samples, arrays):
        if samples is None:
            return budget
        return min(budget, pair_points * samples * arrays * _COMPLEX128_BYTES)

    for surface in surfaces:
        kinds = int(bool(surface.efie)) + int(bool(surface.mfie)) + int(bool(surface.ibc))
        square = float(surface.points) ** 2
        if not streaming and kinds:
            if surface.efie:
                tables += square * (modes + 2) * surface.table_bytes
            if surface.mfie:
                tables += 4.0 * square * (modes + 1) * surface.table_bytes
            if surface.ibc:
                tables += 4.0 * square * (modes + 1) * surface.table_bytes
        near += bor_near_cache_bytes(surface.near_pairs, surface.nodes, kinds, modes)
        if kinds:
            near_workspace = max(near_workspace, 128.0e6)
        if not streaming and kinds:
            if (surface.mfie or surface.ibc) and not kernels.BANDED_FFT:
                fft_workspace = max(fft_workspace, 4.0 * square * signed_modes * _COMPLEX128_BYTES)
            scalar, bracket = surface.fft_samples if surface.fft_samples is not None else (None, None)
            if surface.efie:
                fft_workspace = max(fft_workspace, fft_bytes(square, scalar, 4.0))
            if surface.mfie or surface.ibc:
                fft_workspace = max(fft_workspace, fft_bytes(square, bracket, 18.0 if surface.ibc else 16.0))

    for cross in crosses:
        pair_points = float(cross.points_p) * float(cross.points_q)
        if not streaming:
            tables += pair_points * (modes + 2) * cross.table_bytes
            if cross.has_rotated_pv:
                tables += 4.0 * pair_points * (modes + 1) * cross.table_bytes
            if cross.has_rotated_pv and not kernels.BANDED_FFT:
                fft_workspace = max(fft_workspace, 4.0 * pair_points * signed_modes * _COMPLEX128_BYTES)
            scalar, bracket = cross.fft_samples if cross.fft_samples is not None else (None, None)
            fft_workspace = max(fft_workspace, fft_bytes(pair_points, scalar, 4.0))
            if cross.has_rotated_pv:
                fft_workspace = max(fft_workspace, fft_bytes(pair_points, bracket, 18.0))
        near += bor_cross_near_cache_bytes(cross.near_pairs, modes, cross.has_rotated_pv)
        if cross.near_pairs:
            near_workspace = max(near_workspace, 128.0e6, 64.0e6 + 768 * int(cross.near_max_order) ** 2)

    projection = 0.0
    if constraint_dofs:
        # Categories m = 0, 1 and |m| >= 2 (signed-mode symmetry never builds
        # m = -1).  Every backend stores the transforms sparse: one selection
        # entry per column plus a few relations, priced with CSR overhead
        # (value, column index and row pointer, about 6 complex values per row).
        category_count = 1 if modes == 0 else (2 if modes == 1 else 3)
        projection = category_count * float(constraint_dofs) * 6 * _COMPLEX128_BYTES
    return dict(tables=tables, basis=basis, near=near, projection=projection,
                fft_workspace=fft_workspace, near_workspace=near_workspace)

def estimate_bor_operator_storage_gb(
    m_max: 'int',
    solver_requirements,
    cross_operators=(),
    constraint_dofs: 'int' = 0,
    streaming: 'bool' = False,
) -> 'float':
    """Estimate retained operator auxiliaries and their build workspace.

    ``solver_requirements`` contains ``(solver, efie, mfie, ibc)`` tuples.
    Repeated solver instances are merged so their tables are counted once.
    Cross-surface operators are counted independently.
    ``constraint_dofs`` adds the sparse junction projection transforms retained by
    the partial/multiregion paths.  With ``streaming=True``, far tables and
    their FFT workspace are excluded because the combined streaming planner
    accounts for those blocks and sampling tiles separately; exact same- and
    cross-surface near caches plus junction projections remain included.
    """

    try:
        modes = int(m_max)
        constraint_size = int(constraint_dofs)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            "BoR operator estimates require integer mode and constraint sizes."
        ) from exc
    if modes != m_max or modes < 0:
        raise ValueError("BoR operator mode cap must be a non-negative integer.")
    if constraint_size != constraint_dofs or constraint_size < 0:
        raise ValueError("BoR constraint DOFs must be a non-negative integer.")

    merged = {}
    for requirement in solver_requirements:
        if len(requirement) != 4:
            raise ValueError(
                "Each BoR solver requirement must be (solver, efie, mfie, ibc)."
            )
        solver, efie, mfie, ibc = requirement
        key = id(solver)
        if key in merged:
            previous = merged[key]
            merged[key] = (
                solver,
                previous[1] or bool(efie),
                previous[2] or bool(mfie),
                previous[3] or bool(ibc),
            )
        else:
            merged[key] = (solver, bool(efie), bool(mfie), bool(ibc))

    compressed = compressed_requested()
    streaming = streaming or compressed

    def samples(wavenumber, rho_max, far_gap):
        return (n_xi_for_pairs(wavenumber, rho_max, modes, far_gap, bracket=False),
                n_xi_for_pairs(wavenumber, rho_max, modes, far_gap, bracket=True))

    surfaces = []
    for solver, efie, mfie, ibc in merged.values():
        tabled = not streaming and (efie or mfie or ibc)
        surfaces.append(BorSurfaceStorage(
            int(solver.P), int(solver.Nn), np.dtype(solver._table_dtype).itemsize,
            int(solver._near_pair_count), efie, mfie, ibc,
            samples(solver.k, float(np.max(solver.gen.nodes[:, 0])), float(solver._far_gap())) if tabled else None))
    crosses, seen_crosses = [], set()
    for cross in cross_operators:
        # Derived reverse operators retain nothing of their own.
        if id(cross) in seen_crosses or getattr(cross, 'derived', False):
            continue
        seen_crosses.add(id(cross))
        rho_max = max(float(np.max(cross.sp.gen.nodes[:, 0])), float(np.max(cross.sq.gen.nodes[:, 0])))
        crosses.append(BorCrossStorage(
            int(cross.sp.P), int(cross.sq.P), np.dtype(cross.sp._table_dtype).itemsize,
            len(cross.near_pairs), int(cross.near_max_order),
            samples(cross.k, rho_max, float(cross._far_gap)) if not streaming else None,
            cross.need_p))
    parts = bor_operator_storage_bytes(modes, surfaces, crosses, constraint_size, streaming, compressed)
    retained = parts['tables'] + parts['basis'] + parts['near'] + parts['projection']
    build_workspace = max(parts['fft_workspace'], parts['near_workspace'])
    return (BOR_RETAINED_STORAGE_FACTOR * retained + build_workspace) / 1.0e9
