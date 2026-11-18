"""Sparse pole/junction constraints and bounded modal matrix operations."""
import numpy as np
from scipy.sparse import csr_matrix, issparse
from ghost_backend.bor.tiled import TileExpression, modal_block


class _ConstraintEntries:
    """Builder of a pole/junction transform ``Q = S + E``.

    ``S`` selects the active full-system rows (one column each, value 1);
    ``E`` holds the few relations of inactive rows (axis-pole phi components,
    junction slaves) to their master columns.  Item assignment records ``E``
    with matrix semantics (the last value written to a position wins), so
    the existing ``Q[row, column] = value`` code builds it unchanged.
    """

    def __init__(self, n_rows: 'int', n_cols: 'int'):
        self.shape = (int(n_rows), int(n_cols))
        self.primary = np.full(int(n_cols), -1, dtype=np.intp)
        self.extra: 'Dict[Tuple[int, int], complex]' = {}

    def select(self, rows, columns) -> 'None':
        self.primary[np.asarray(columns, dtype=np.intp)] = np.asarray(rows, dtype=np.intp)

    def __setitem__(self, key, value) -> 'None':
        row, column = key
        self.extra[(int(row), int(column))] = complex(value)

    def tocsr(self):
        if np.any(self.primary < 0):
            raise ValueError("BoR constraint transform has a column without an active row.")
        extra = sorted(self.extra.items())
        extra_rows = np.array([rc[0] for rc, _ in extra], dtype=np.intp)
        extra_cols = np.array([rc[1] for rc, _ in extra], dtype=np.intp)
        extra_vals = np.array([value for _, value in extra], dtype=complex)
        if np.intersect1d(extra_rows, self.primary).size:
            raise ValueError("BoR constraint relations must act on inactive rows.")
        rows = np.concatenate([self.primary, extra_rows])
        cols = np.concatenate([np.arange(self.shape[1], dtype=np.intp), extra_cols])
        data = np.concatenate([np.ones(self.shape[1], dtype=complex), extra_vals])
        Q = csr_matrix((data, (rows, cols)), shape=self.shape)
        Q._ghost_constraint = (self.primary.copy(), extra_rows, extra_cols, extra_vals)
        return Q

def _constraint_structure(transform):
    """``(primary, extra_rows, extra_cols, extra_vals)`` with ``Q = S + E``.

    Transforms built by ``_ConstraintEntries`` carry it; otherwise it is
    inferred when unambiguous (every column has exactly one row whose only
    entry is 1, as in the block-diagonal pole transforms) or None.
    """
    explicit = getattr(transform, '_ghost_constraint', None)
    if explicit is not None:
        return explicit
    q = transform.tocsr() if issparse(transform) else csr_matrix(transform)
    n_rows, n_cols = q.shape
    counts = np.diff(q.indptr)
    rows = np.repeat(np.arange(n_rows), counts)
    single = counts[rows] == 1
    is_primary = single & (q.data == 1.0)
    primary_cols = q.indices[is_primary]
    if primary_cols.size != n_cols or np.unique(primary_cols).size != n_cols:
        return None
    primary = np.empty(n_cols, dtype=np.intp)
    primary[primary_cols] = rows[is_primary]
    extra = ~is_primary
    if np.intersect1d(rows[extra], primary).size:
        return None
    return primary, rows[extra], q.indices[extra].astype(np.intp), q.data[extra]

def _reduce_constrained_operator(matrix, transform):
    """``Q^H A Q`` for sparse pole/junction relations.

    With ``Q = S + E`` (selection plus a few relations of inactive rows) this
    is one gathered copy of ``A`` plus rank-one row/column updates -- the
    generalization of ``BorPecSolver.reduce_pole_operator``.  The former
    sparse product copied ``A`` about three times (SciPy ravels F-ordered
    operands) and ran 6.7x slower at 2,400 unknowns.
    """
    if isinstance(matrix, TileExpression):
        return matrix.reduce(transform)
    structure = _constraint_structure(transform)
    if structure is None:
        q = csr_matrix(transform)
        return q.conj().T @ (q.T @ matrix.T).T
    primary, extra_rows, extra_cols, extra_vals = structure
    reduced = matrix[np.ix_(primary, primary)]
    for row, column, value in zip(extra_rows, extra_cols, extra_vals):
        reduced[:, column] += value * matrix[primary, row]
        reduced[column, :] += np.conj(value) * matrix[row, primary]
    for row, column, value in zip(extra_rows, extra_cols, extra_vals):
        for row2, column2, value2 in zip(extra_rows, extra_cols, extra_vals):
            reduced[column, column2] += np.conj(value) * value2 * matrix[row, row2]
    return reduced

def _constraint_coordinates(full_coordinates, transform):
    """Positions of reduced unknowns; used only to order a checked factor.

    Selecting each constraint's primary unknown preserves colocated electric
    and magnetic components. General sparse relations use a weighted centroid;
    neither choice changes matrix entries or the original-matrix checks.
    """
    structure = _constraint_structure(transform)
    if structure is not None:
        return np.asarray(full_coordinates)[structure[0]]
    weights = abs(csr_matrix(transform))
    totals = np.asarray(weights.sum(axis=0)).ravel()
    return (weights.T @ np.asarray(full_coordinates)) / np.maximum(totals[:, None], 1e-300)

def _rotate_test_rows(matrix, nodes):
    """Test n x field in (t, phi) coordinates: (-field_phi, field_t)."""
    return modal_block([[-matrix[nodes:, :]], [matrix[:nodes, :]]])

def _mix_dual_ibc_in_place(quads, alpha, scale, weights, chunk_rows: 'int' = 256) -> 'None':
    """Turn the EFIE quadrants ``T`` into ``alpha*T + scale*dual(T)*diag(w)``.

    ``dual(T) = [[T_ff, -T_ft], [-T_tf, T_tt]]`` is the EFIE operator acting on
    the magnetic current ``M = -Zs n x J`` of an impedance surface; ``w`` is the
    scalar impedance or the nodal impedance applied to the source columns.
    The quadrant pairs (tt, ff) and (tf, ft) are mixed through row chunks, so
    no second full matrix is ever formed (the former path held ``Z``, the dual
    copy and its column-scaled product at once).
    """
    tt, tf, ft, ff = quads
    columns = weights if np.ndim(weights) == 0 else np.asarray(weights)[None, :]
    rows = tt.shape[0]
    for start in range(0, rows, chunk_rows):
        piece = slice(start, min(rows, start + chunk_rows))
        a, d = tt[piece].copy(), ff[piece].copy()
        tt[piece] = alpha * a + scale * (d * columns)
        ff[piece] = alpha * d + scale * (a * columns)
        b, c = tf[piece].copy(), ft[piece].copy()
        tf[piece] = alpha * b - scale * (c * columns)
        ft[piece] = alpha * c - scale * (b * columns)

def _scaled_add_into(target, source, scale, chunk_rows: 'int' = 256):
    """``target += scale * source`` through bounded row chunks.

    ``source`` may alias read-only single-precision storage; only a
    ``chunk_rows``-row temporary is ever formed, so a full-matrix copy is
    never needed to combine one operator family into the system matrix.
    """
    if scale == 0:
        return
    rows = target.shape[0]
    for start in range(0, rows, chunk_rows):
        stop = min(rows, start + chunk_rows)
        piece = source[start:stop]
        if scale == 1:
            target[start:stop] += piece
        else:
            target[start:stop] += piece * scale
