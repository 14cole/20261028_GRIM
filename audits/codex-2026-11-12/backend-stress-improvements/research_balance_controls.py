"""Small independent algebra checks; not a physical-coating accuracy proof."""
import json,sys
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent;sys.path.insert(0,str(Path(sys.argv[1])/'tools/GHOST'))
from ghost_backend.linalg.workspace import equilibrated_scaling_and_norm_1
from ghost_backend.twod.formulations.combined_regions import balanced_condition_scaling
rng=np.random.default_rng(20261112);size=24;rows=[]
q,_=np.linalg.qr(rng.normal(size=(size,size)));v,_=np.linalg.qr(rng.normal(size=(size,size)))
for smallest in (1.,1e-3,1e-9,1e-12):
 a=q@np.diag(np.geomspace(1,smallest,size))@v.T
 a=np.diag(np.r_[np.ones(size//2),np.full(size//2,1e3)])@a@np.diag(np.r_[np.ones(size//2),np.full(size//2,1e-2)])
 scale=equilibrated_scaling_and_norm_1(a)
 balanced=balanced_condition_scaling(a,scale,np.array([0,size//2]))
 mats=[a/r[:,None]/c[None,:] for r,c,_ in (scale,balanced)]
 # independently form scaled matrices and compare their exact norms
 assert np.isclose(np.linalg.norm(mats[1],1),balanced[2],rtol=1e-13)
 cond=[float(np.linalg.cond(m,1)) for m in mats]
 rows.append(dict(smallest_unscaled_singular_value=smallest,max_equilibrated_condition=cond[0],block_balanced_condition=cond[1]))
 if smallest<=1e-9:assert cond[1]>1e6,'Balancing hid deliberately near-null test'
(P/'checks'/'research-balance-controls.json').write_text(json.dumps(dict(passed=True,rows=rows,caveat='Synthetic algebra checks only; no continuum or coating validation.'),indent=2)+'\n')
print(rows)
