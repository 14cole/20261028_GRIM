import os,sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST'))
from dense_layout import install
install()
from ghost_backend.linalg.dense import DenseFactor
from ghost_backend.execution.options import execution_scope,cpu_allocation_scope
rng=np.random.default_rng(3191);records=[]
for n in (70,300):
    a=np.asfortranarray(np.eye(n)+.01*(rng.normal(size=(n,n))+1j*rng.normal(size=(n,n))))
    saved=a.copy();b=rng.normal(size=(n,5))+1j*rng.normal(size=(n,5));b[:,2]=0
    with cpu_allocation_scope(1),execution_scope({'factorization':'dense','dense_residual_storage':'memory','assembly_threads':1,'blas_threads':1}):
        f=DenseFactor(a,owned_matrix=True,force_double=True,diagnostics={})
        x=f.solve(b);ref=np.linalg.solve(saved,b)
        error=float(np.linalg.norm(x-ref)/np.linalg.norm(ref));assert error<1e-12
        assert f.a.flags.c_contiguous and np.array_equal(f.a,saved) and np.shares_memory(f.lu,a)
        trans_errors=[]
        for trans,op in ((0,saved),(1,saved.T),(2,saved.conj().T)):
            got=f._solve_lu(b,trans=trans);expected=np.linalg.solve(op,b)
            err=float(np.linalg.norm(got-expected)/np.linalg.norm(expected));assert err<1e-12
            trans_errors.append(err)
        f.restore_original();assert np.array_equal(a,saved)
        records.append(dict(n=n,error=error,trans_errors=trans_errors,original_restored_bitwise=True,event=f.event))
Path(__file__).with_name('layout-check.json').write_text(json.dumps(records,indent=2))
print(json.dumps(records))
