"""Bounded coefficient queries for independent research solve validation."""
import numpy as np
from ghost_backend.compressed.hmatrix import QUERY_ENTRIES

def query_tiles(row_count, column_count, entries=QUERY_ENTRIES, preferred_rows=32):
    """Cover a rectangular query exactly once within the oracle's entry cap."""
    if row_count < 0 or column_count < 0 or entries < 1 or preferred_rows < 1:
        raise ValueError('Invalid query dimensions or capacity')
    if not row_count or not column_count:return
    rows=max(1,min(preferred_rows,entries//column_count))
    cols=max(1,min(column_count,entries//rows))
    for a in range(0,row_count,rows):
        for b in range(0,column_count,cols):
            yield slice(a,min(row_count,a+rows)),slice(b,min(column_count,b+cols))

def exact_rows(oracle, sample, unknowns):
    # Preallocate once: concatenating a list retains all chunks and a second
    # full copy. The query cap accounts for coefficients AND error estimates.
    result=np.empty((len(sample),unknowns),complex);calls=0;max_entries=0
    for rr,cc in query_tiles(len(sample),unknowns):
        rows=sample[rr];cols=np.arange(cc.start,cc.stop)
        result[rr,cc]=oracle.get(rows,cols)
        calls+=1;max_entries=max(max_entries,len(rows)*len(cols))
    return result,dict(query_calls=calls,max_query_entries=max_entries,query_entry_cap=QUERY_ENTRIES,
                       retained_exact_row_bytes=result.nbytes)


def validate_rows(oracle, sample, unknowns, x, b, entries=QUERY_ENTRIES):
    """Exact sampled residuals without retaining the sampled coefficient matrix."""
    residual=np.zeros((len(sample),x.shape[1]),complex)
    norms=np.zeros(len(sample));calls=0;max_entries=0
    for rr,cc in query_tiles(len(sample),unknowns,entries=entries):
        coeff=oracle.get(sample[rr],np.arange(cc.start,cc.stop))
        residual[rr]+=coeff@x[cc]
        norms[rr]+=np.sum(abs(coeff),axis=1)
        calls+=1;max_entries=max(max_entries,coeff.size)
    residual-=b[sample]
    denominator=norms[:,None]*np.max(abs(x),axis=0)+abs(b[sample])
    with np.errstate(invalid='ignore',divide='ignore'):
        errors=np.max(abs(residual)/denominator,axis=0)
    return errors,residual,norms,dict(query_calls=calls,max_query_entries=max_entries,query_entry_cap=entries,
        retained_exact_row_bytes=0,avoided_full_row_buffer_bytes=len(sample)*unknowns*16,
        validation='streamed exact coefficient rows; no stored coefficient matrix')
