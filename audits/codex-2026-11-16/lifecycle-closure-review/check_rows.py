"""Independent row-query attribution with actual BLAS-pool checks; no solve."""
import os,sys,json,hashlib,time
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_info,threadpool_limits
sys.path.insert(0,os.environ['MONOSTATIC_AUDIT'])
from monostatic import mesh_for,SimpleNamespace,NativeOracle,CPUState,_STATE,cpu_allocation_scope,execution_scope,exact_rows
R=Path(__file__).resolve().parent;D=R/'results';D.mkdir(exist_ok=True)
if (D/'rows.json').exists():raise RuntimeError('Refusing overwrite')
z=np.load(R/'prior/star-control.npz');saved=np.load(R/'claude/star_residuals/star8192-residuals-t1-and-t4.npz')
sha=lambda a:hashlib.sha256(a.tobytes(order='C')).hexdigest()
n=4096;k=80.;eps=3-.08j
mesh=mesh_for(n,'star');info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
reference=None;seen={};records=[];arrays={}
for assembly,blas,label in [(1,1,'a1b1'),(2,1,'a2b1'),(3,1,'a3b1'),(4,1,'a4b1'),(1,4,'a1b4'),(4,4,'a4b4'),(1,1,'a1repeat'),(4,1,'a4repeat')]:
    t=time.perf_counter()
    with threadpool_limits(limits=blas,user_api='blas'),_STATE.override(CPUState(kernel_only=True)),cpu_allocation_scope(assembly),execution_scope({'assembly_threads':assembly,'blas_threads':blas}):
        pools=[dict(prefix=p['prefix'],threads=p['num_threads'],version=p['version']) for p in threadpool_info() if p['user_api']=='blas']
        assert pools and all(p['threads']==blas for p in pools),pools
        oracle=NativeOracle(mesh,[info],'TE',k,'dielectric');e,query=exact_rows(oracle,z['rows'],2*n)
        residual=e@z['density']-z['rhs'][z['rows']];norm=np.sum(abs(e),axis=1)
        after=[p['num_threads'] for p in threadpool_info() if p['user_api']=='blas'];assert all(t==blas for t in after)
    if reference is None:reference=e.copy()
    changed=np.flatnonzero(e.ravel()!=reference.ravel());old=reference.ravel()[changed];new=e.ravel()[changed];delta=abs(new-old)
    denom=norm[:,None]*np.max(abs(z['density']),axis=0)+abs(z['rhs'][z['rows']])
    backward=float(np.max(abs(residual)/denom));assert backward<1e-12
    rec=dict(label=label,assembly_threads=assembly,blas_threads=blas,blas_pools=pools,query=query,seconds=time.perf_counter()-t,
        exact_sha256=sha(e),residual_sha256=sha(residual),different_entries=len(changed),entries=e.size,
        max_abs_coefficient_difference=float(delta.max()) if len(delta) else 0.,max_relative_changed_entry=float(np.max(delta/abs(old))) if len(delta) else 0.,
        row_norm_matches_control=bool(np.array_equal(norm,z['row_norm'])),max_backward_error=backward,
        matches_saved_t1=residual.tobytes()==saved['residual_t1'].tobytes(),matches_saved_t4=residual.tobytes()==saved['residual_t4'].tobytes())
    if assembly in seen:assert sha(e)==seen[assembly]
    else:seen[assembly]=sha(e)
    arrays[label+'_changed_flat_indices']=changed;arrays[label+'_reference_values']=old;arrays[label+'_values']=new
    arrays[label+'_residual']=residual;arrays[label+'_row_norm']=norm
    records.append(rec);print(json.dumps(rec),flush=True)
assert seen[1]==seen[2] and seen[3]!=seen[1] and seen[4]!=seen[1]
assert all(r['matches_saved_t1'] for r in records if r['assembly_threads'] in (1,2))
assert all(r['matches_saved_t4'] for r in records if r['assembly_threads']==4)
np.savez_compressed(D/'row-evidence.npz',**arrays)
(D/'rows.json').write_text(json.dumps(records,indent=2))
