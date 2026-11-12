"""Independent normal/transpose/adjoint inverse-action checks for audit hook."""
import json,sys
from pathlib import Path
import numpy as np
import scipy.linalg as la
P=Path(__file__).resolve().parent;sys.path.insert(0,str(Path(sys.argv[1])/'tools/GHOST'))
from research_hooks import install_scaled_lu
rng=np.random.default_rng(310);a=rng.normal(size=(32,32))+1j*rng.normal(size=(32,32))+32*np.eye(32)
a=np.geomspace(.01,100,32)[:,None]*a*np.geomspace(.01,100,32)[None,:]
hits=install_scaled_lu();lu,piv=la.lu_factor(a.copy(order='F'),overwrite_a=True);rows=[]
for trans in (0,1,2):
    matrix=a if trans==0 else a.T if trans==1 else a.conj().T
    for columns in (1,3):
        wanted=rng.normal(size=(32,columns))+1j*rng.normal(size=(32,columns))
        rhs=matrix@wanted
        if columns==1:rhs=rhs[:,0];wanted=wanted[:,0]
        actual=la.lu_solve((lu,piv),rhs,trans=trans)
        error=float(np.max(abs(actual-wanted))/np.max(abs(wanted)))
        backward=float(np.max(abs(matrix@actual-rhs))/(np.linalg.norm(matrix,np.inf)*np.max(abs(actual))+np.max(abs(rhs))))
        assert error<1e-9 and backward<1e-12
        rows.append(dict(transpose_mode=trans,columns=columns,relative_solution_error=error,backward_error=backward))
(P/'checks'/'research-scaled-lu-controls.json').write_text(json.dumps(dict(passed=True,rows=rows,factors=hits),indent=2)+'\n')
print(rows)
