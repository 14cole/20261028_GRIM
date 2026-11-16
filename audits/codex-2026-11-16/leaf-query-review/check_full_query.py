"""Fresh full retained-operator query allocations on controlled dense block rows."""
import os,sys,json,tracemalloc
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST'))
from ghost_backend.compressed.hmatrix import BlockRow,HMatrixOperator
from query_hook import install
old=BlockRow.values;install();new=BlockRow.values
def run(op,ids,fn):
    BlockRow.values=fn;tracemalloc.start();tracemalloc.reset_peak()
    result=op._get_positions(ids,ids)
    _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    return result,peak
out=[]
for size in (149,512,1024):
    width=4096;u=np.arange(size*width,dtype=float).reshape(size,width).astype(complex)
    row=BlockRow(0,0,size,[(0,width)],u,None)
    op=object.__new__(HMatrixOperator);op.levels=[(np.array([0]),np.array([size]),[[row]])]
    ids=np.arange(size,dtype=np.int64)
    a,before=run(op,ids,old);b,after=run(op,ids,new);assert np.array_equal(a,b)
    q=16*size*size;assert after>2*q and after<4*q+1024**2
    out.append(dict(query_size=size,partner_width=width,original_peak_bytes=before,direct_peak_bytes=after,
        original_allowance_bytes=2*q,proposed_allowance_bytes=4*q+1024**2,bit_identical=True))
    del a,b,u,row,op
Path(__file__).with_name('full-query-check.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
