"""Compare complete new densities and fields with archived Dense references."""
import json,os
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
AUDIT=Path(os.environ['MONOSTATIC_AUDIT'])
records=[]
for geometry,pol in (('square','TE'),('slot','TE'),('slot','TM')):
    name=f'{geometry}-1024-180-{pol}-right'
    reference=f'{geometry}-1024-180-dense-cold' if pol=='TE' else 'slot-1024-180-TM-dense'
    d=json.loads((HERE/'reproduced'/f'{name}.json').read_text())
    with np.load(HERE/'reproduced'/f'{name}-batch0000.npz') as f: a={k:np.ascontiguousarray(f[k]) for k in f.files}
    with np.load(AUDIT/'restored/results'/f'{reference}.npz') as f:b={k:np.ascontiguousarray(f[k]) for k in f.files}
    assert np.array_equal(a['angles'],b['angles'])
    assert all(np.isfinite(v).all() for v in a.values())
    rhs=float(np.max(np.linalg.norm(a['rhs']-b['rhs'],axis=0)/np.linalg.norm(b['rhs'],axis=0)))
    field=float(np.max(abs(a['field']-b['field']))/np.max(abs(b['field'])))
    density=float(np.max(np.linalg.norm(a['density']-b['density'],axis=0)/np.linalg.norm(b['density'],axis=0)))
    backward=float(np.max(abs(a['residual'])/(a['row_norm'][:,None]*np.max(abs(a['density']),axis=0)+abs(a['rhs'][a['rows']]))))
    true=max(x['max_scaled_relative_residual'] for x in d['block_krylov'])
    assert rhs<5e-15 and field<1e-8 and density<1e-7 and backward<1e-12 and true<=1e-12
    records.append(dict(case=name,reference=reference,rhs_difference=rhs,field_difference=field,density_difference=density,exact_row_backward_error=backward,max_true_relative_residual=true,compute_seconds=d['compute_seconds'],peak_gib=d['peak_gib'],applications=sum(x['rhs_equivalent_matrix_applications'] for x in d['block_krylov'])))
(HERE/'physical-checks.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps(records,indent=2))
