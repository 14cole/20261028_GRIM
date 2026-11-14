"""Actual HMatrix/HODLR inverse as preconditioner for a panel-moment FMM.

Research only: a deliberately loose preconditioner operator must not pass the
production operator release gate. Accurate FMM and exact coefficient rows
check the outer solve. No global dense matrix is made until optional small
case reference validation, after the capacity peak has been recorded.
"""
import os, sys, json, time, resource, gc, weakref
from pathlib import Path
import numpy as np
from scipy.sparse.linalg import gmres, LinearOperator
sys.path.insert(0, os.environ.get('GRIM_ROOT', '/workspace/grim-fmm-followup')+'/tools/GHOST')
from ghost_backend.compressed.coefficients import NativeOracle
from ghost_backend.compressed.hmatrix import HMatrixOperator, HMatrixRejected, support_radius
from ghost_backend.compressed.hmatrix_factor import HMatrixSystem
from ghost_backend.execution.options import cpu_allocation_scope, execution_scope
from ghost_backend.twod.formulations import dielectric
from ghost_backend.twod.assembly.mass import sparse_mass
from ghost_backend.twod import operators as op
from fmm_galerkin import circle_mesh
from moment_hybrid import MomentHybrid, array_bytes
from types import SimpleNamespace


class PreconditionerOperator(HMatrixOperator):
    def _validate(self):
        self.production_gate_passed = True
        try:
            super()._validate()
        except HMatrixRejected:
            self.production_gate_passed = False
            measured = max(self.sampled_row_error, self.scaled_sampled_row_error)
            if not np.isfinite(measured) or measured > 10*self.tolerance:
                raise


def main(spec):
    started = time.perf_counter(); rss = lambda: resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20
    def stage(name, **kw):
        print(json.dumps(dict(stage=name, elapsed=time.perf_counter()-started, peak_gib=rss(), **kw)), file=sys.stderr, flush=True)
    n, k0 = spec['n'], spec['k']; pol=spec.get('pol','TE'); eps=complex(*spec.get('eps',[3.,-.08])); k1=k0*np.sqrt(eps)
    mesh=circle_mesh(n, star=spec.get('star',True), inward=True); nd=2*n
    info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k1,k_minus=k0,plus_region=1,minus_region=0)
    coords=np.tile(np.asarray([node.xy for node in mesh.nodes]),(2,1))
    oracle=NativeOracle(mesh,[info],pol,k0,'dielectric')
    start=time.perf_counter()
    from preconditioner_storage import packed_operator_blocks,finish_operator
    precision=spec.get('preconditioner_storage','complex128')
    if precision not in ('complex128','complex64'):raise ValueError('Unknown preconditioner storage')
    with packed_operator_blocks(precision=='complex64') as storage:
        h=PreconditionerOperator(oracle,coords,radius=support_radius(mesh,coords),tolerance=spec.get('op_tol',1e-3),budget=4*2**30)
    finish_operator(h,storage)
    op_seconds=time.perf_counter()-start; stage('compressed_operator',bytes=h.bytes)
    rows,cols,_=h.equilibrate()
    start=time.perf_counter()
    inv=HMatrixSystem(h,coords,tolerance=spec.get('inv_tol',1e-3),budget=4*2**30,checkpoint=None)
    inv_seconds=time.perf_counter()-start; peak_pre=rss(); stage('compressed_inverse',bytes=inv.bytes)
    hbytes, hevidence, gate = h.bytes, h.evidence, h.production_gate_passed
    sample=np.unique(np.r_[h.order[h.sample_rows],np.random.default_rng(20261114).choice(nd,min(64,nd),replace=False)])
    before_release=array_bytes(inv); detach_errors=[]; released=False
    if spec.get('detach_operator',True):
        # Construction uses h; root.solve uses only the retained inverse tree.
        # Check vector-batch and transpose/adjoint actions before releasing h.
        rng=np.random.default_rng(42);probe=rng.normal(size=(nd,2))+1j*rng.normal(size=(nd,2))
        controls=[inv.apply(probe,solve=True,trans=t) for t in (0,1,2)]
        ref=weakref.ref(h);inv.operator=None;del h;gc.collect();released=ref() is None
        for t,control in enumerate(controls):
            err=float(np.max(abs(inv.apply(probe,solve=True,trans=t)-control)))
            assert err==0,err
            detach_errors.append(err)
        assert released,'Construction operator remains retained'
        del probe,controls,control
    pre_bytes=array_bytes(inv)
    stage('preconditioner_ready',reachable_bytes=pre_bytes,released_operator=released)
    pre=LinearOperator((nd,nd),matvec=lambda v:cols*inv.apply(rows*v,solve=True),dtype=complex)
    start=time.perf_counter()
    ex=MomentHybrid(mesh,k0,mode=spec.get('near','hybrid_nodal')); inter=MomentHybrid(mesh,k1,mode=spec.get('near','hybrid_nodal'))
    fmm_seconds=time.perf_counter()-start; mass=sparse_mass(mesh); factor=1/eps if pol=='TE' else 1.
    def apply(x):
        u,v=x[:n],x[n:]
        return np.concatenate((.5*(mass@u)+ex.apply(u,'K')+1j*k0*ex.apply(u,'S')-inter.apply(v,'S'),
            ex.apply(u,'W')-1j*k0*ex.apply(u,'KP')+.5j*k0*(mass@u)+factor*(inter.apply(v,'KP')+.5*(mass@v))))
    lin=LinearOperator((nd,nd),matvec=lambda v:apply(v/cols)/rows,dtype=complex)
    stage('fmm_ready',bytes=ex.retained_bytes+inter.retained_bytes)
    angles=np.asarray(spec.get('angles',[0.,47.])); b=dielectric.rhs_many(mesh,k0,angles); solutions=[]; results=[]
    start=time.perf_counter()
    for i in range(len(angles)):
        hist=[]; ts=time.perf_counter()
        y,status=gmres(lin,b[:,i]/rows,M=pre,rtol=1e-12,atol=0,restart=80,maxiter=10,callback=lambda r:hist.append(float(r)),callback_type='pr_norm')
        x=y/cols; solutions.append(x)
        residual=apply(x)-b[:,i]
        results.append(dict(angle=float(angles[i]),iterations=len(hist),status=int(status),seconds=time.perf_counter()-ts,
            scaled_relative_residual=float(np.linalg.norm(residual/rows)/np.linalg.norm(b[:,i]/rows)),history=hist))
        stage('angle_done',**{k:v for k,v in results[-1].items() if k!='history'})
    solve_seconds=time.perf_counter()-start; peak_capacity=rss(); x=np.column_stack(solutions)
    from exact_validation import validate_rows
    row_errors,residual,row_norms,validation_queries=validate_rows(oracle,sample,nd,x,b)
    if any(r['status'] != 0 for r in results) or not np.all(np.isfinite(row_errors)) or np.max(row_errors)>1e-12:
        raise RuntimeError('Research solve failed GMRES or independent exact-row checks')
    obs=np.arange(0.,360.,2.)
    field=op._farfield_linear_density_many(mesh,x[:n],k0,obs,'DLP',projection='grid')+1j*k0*op._farfield_linear_density_many(mesh,x[:n],k0,obs,'SLP',projection='grid')
    out=Path(spec['out']); np.savez_compressed(str(out)+'.npz',density=x,field=field,angles=angles,observation=obs,rows=sample,exact_row_residual=residual,exact_row_norm=row_norms,rhs=b,row_scale=rows,column_scale=cols)
    result=dict(spec,unknowns=nd,compressed_operator_seconds=op_seconds,compressed_inverse_seconds=inv_seconds,fmm_setup_seconds=fmm_seconds,
        operator_bytes=hbytes,inverse_bytes=inv.bytes,fmm_bytes=ex.retained_bytes+inter.retained_bytes,preconditioner_reachable_array_bytes=pre_bytes,
        preconditioner_bytes_before_release=before_release,construction_operator_released=released,detach_absolute_errors=detach_errors,
        peak_preconditioner_gib=peak_pre,peak_before_reference_gib=peak_capacity,solve_seconds=solve_seconds,results=results,
        peak_through_validation_gib=rss(),
        exact_sampled_rowwise_backward_error=row_errors.tolist(),sampled_rows=len(sample),operator_evidence=hevidence,inverse_evidence=inv.evidence,
        loose_operator_passes_production_gate=gate,dense_reference_live_during_capacity=False,production_certified=False)
    result['preconditioner_storage_evidence']=storage
    import safe_cross
    result['unseen_components']=safe_cross.UNSEEN_COMPONENTS.copy()
    result['validation_queries']=validation_queries
    result['near_details']={name:dict(kernel_seconds=value.kernel_seconds,queried_pairs=value.queried_pairs,near_bytes=value.near_bytes,setup_seconds=value.setup_seconds) for name,value in [('exterior',ex),('interior',inter)]}
    result['validated_solve_seconds']=time.perf_counter()-started
    if spec.get('dense_reference',False):
        from scipy.linalg import solve
        a=dielectric.assemble_system(mesh,[info],pol,k0)
        ref=solve(a/rows[:,None]/cols[None,:],b/rows[:,None])/cols[:,None]
        rf=op._farfield_linear_density_many(mesh,ref[:n],k0,obs,'DLP',projection='grid')+1j*k0*op._farfield_linear_density_many(mesh,ref[:n],k0,obs,'SLP',projection='grid')
        np.savez_compressed(str(out)+'-dense.npz',density=ref,field=rf)
        result.update(field_relative_max_error=float(np.max(abs(field-rf))/np.max(abs(rf))),
            dense_full_relative_residual=float(np.max(np.linalg.norm(a@x-b,axis=0)/np.linalg.norm(b,axis=0))),
            dense_full_backward_error=float(np.max(abs(a@x-b)/(np.linalg.norm(a,np.inf)*np.max(abs(x),axis=0)+np.max(abs(b),axis=0)))))
    result['wall_seconds']=time.perf_counter()-started
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    with cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):main(json.loads(sys.argv[1]))
