from ref import *
import ghost_backend.twod.operators as ops
from ghost_backend.twod.assembly.kernels import KernelTable, values, table_reach
import warnings, functools; warnings.simplefilter('ignore')
print=functools.partial(print,flush=True)
h=0.01; e=elem((0,0),(h,0),0)
print("self S block rel err vs mpmath (|kL|, arg k deg): ")
for kl in (40.0,600.0):
    row=[]
    for arg in (0,-60):
        k=kl/h*np.exp(1j*np.radians(arg)); k=k.real if arg==0 else k
        if kl>=100 and arg in(-30,): continue
        try:
            S=ops._single_layer_block_linear(e,e,k); many=ops._single_layer_self_blocks_exact_many([h],k)[0]
            R=ref_self(h,k,dps=25)
            row.append(f"{arg}: {relerr(S,R):.1e}"+("" if many is None else ("" if np.array_equal(many,S) else " MANY-DIFF")))
        except Exception as ex: row.append(f"{arg}: EXC {str(ex)[:60]}")
    print(f"  kL={kl}: "+" | ".join(row))
