"""Research monostatic sweeps. No production source modifications or certification.
One JSON spec argument; all timings are perf_counter seconds. Each process owns one factor.
"""
import os,sys,json,time,resource,gc,weakref
from pathlib import Path
import numpy as np
import scipy.linalg as la
from scipy.sparse.linalg import LinearOperator,gmres,lgmres
HERE=Path(__file__).resolve().parent
ROOT=Path(os.environ['GRIM_ROOT'])
sys.path[:0]=[str(ROOT/'tools/GHOST'),str(HERE/'research')]
from ghost_backend.execution.cpu import CPUState,_STATE
from ghost_backend.execution.options import cpu_allocation_scope,execution_scope
from ghost_backend.twod.formulations import dielectric
from ghost_backend.twod import operators as op
from ghost_backend.twod.geometry import LinearNode,LinearElement,LinearMesh
from ghost_backend.compressed.coefficients import NativeOracle
from ghost_backend.compressed.hmatrix import HMatrixOperator,support_radius
from ghost_backend.compressed.hmatrix_factor import HMatrixFactor,HMatrixSystem
from ghost_backend.linalg.dense import DenseFactor
from ghost_backend.linalg.sweep import SweepBasis,solve as sweep_solve,_qr_basis
from ghost_backend.twod.assembly.mass import sparse_mass
from preconditioned_solve import PreconditionerOperator
from preconditioner_storage import packed_operator_blocks,finish_operator
from moment_hybrid import MomentHybrid,array_bytes
from exact_validation import exact_rows
from fmm_galerkin import circle_mesh
from types import SimpleNamespace

def mesh_for(n,kind):
    if kind=='star': return circle_mesh(n,star=True,inward=True)
    vertices={'square':[[-1,-1],[1,-1],[1,1],[-1,1]],
              'slot':[[-1,-1],[1,-1],[1,1],[.01,1],[.01,-.5],[-.01,-.5],[-.01,1],[-1,1]]}[kind]
    v=np.asarray(vertices,float); assert n%len(v)==0
    # Equal panels per straight edge; the narrow slot base therefore has finer panels.
    xy=np.concatenate([a+(b-a)*np.arange(n//len(v))[:,None]/(n//len(v)) for a,b in zip(v,np.roll(v,-1,axis=0))])
    nodes=[LinearNode(p,(i,0)) for i,p in enumerate(xy)];elements=[]
    for i,p in enumerate(xy):
        j=(i+1)%n;d=xy[j]-p;l=float(la.norm(d));t=d/l
        elements.append(LinearElement('body',2,0,0,0,(i,j),p,xy[j],(p+xy[j])/2,t,np.array([-t[1],t[0]]),l,i))
    return LinearMesh(nodes,elements)

def main(spec):
    started=time.perf_counter();io_path=Path('/proc/self/io');io_start={k:int(v) for k,v in (line.split(':') for line in io_path.read_text().splitlines())} if io_path.exists() else {};out=Path(spec['out']);out.parent.mkdir(parents=True,exist_ok=True)
    rss=lambda:resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20
    record=dict(spec=spec,production_certified=False,mesh_certified=False,stages={},batches=[],angles=[])
    def stage(name,t,**kw):
        d=dict(seconds=time.perf_counter()-t,peak_gib=rss(),**kw);record['stages'][name]=d
        print(json.dumps(dict(stage=name,**d)),file=sys.stderr,flush=True)
    n=spec['n'];nd=2*n;k=spec['k'];eps=complex(3.,-.08);pol=spec.get('pol','TE')
    mesh=mesh_for(n,spec.get('geometry','star'))
    angles=np.linspace(spec.get('start',0.),spec.get('stop',360.),spec['count'],endpoint=False)
    # GHOST incidence angle is the direction toward the source; matched observation
    # uses that same angle, as in production fields._solve_fields (not angle+180).
    info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
    coords=np.tile(np.array([v.xy for v in mesh.nodes]),(2,1));oracle=NativeOracle(mesh,[info],pol,k,'dielectric')
    method=spec['method'];pre_calls=[0];a_calls=[0]
    if method in ('dense','compressed'):
        t=time.perf_counter()
        if method=='dense':a=dielectric.assemble_system(mesh,[info],pol,k)
        else:a=HMatrixOperator(oracle,coords,radius=support_radius(mesh,coords),budget=12*2**30)
        stage('assembly',t,operator_bytes=a.nbytes if method=='dense' else a.bytes)
        t=time.perf_counter()
        fac=DenseFactor(a,owned_matrix=True,force_double=True) if method=='dense' else HMatrixFactor(a,storage_budget_bytes=12*2**30)
        stage('factor',t)
        if method=='dense' and spec.get('residual_storage')=='disk':assert fac.event.get('residual_storage')=='disk',fac.event
        if spec.get('pack_inverse'):
            assert method=='compressed'
            inv=fac.factor;saved=[0];before=array_bytes(inv)
            probe=np.random.default_rng(412).normal(size=(nd,2))+1j*np.random.default_rng(413).normal(size=(nd,2))
            controls=[inv.apply(probe,solve=True,trans=i) for i in (0,1,2)]
            def pack(node):
                for key in ('v12','v21','e1','e2'):
                    ar=getattr(node,key,None)
                    if ar is not None:
                        small=ar.astype(np.complex64)
                        assert np.isfinite(small).all() and not np.any((ar!=0)&(small==0))
                        saved[0]+=ar.nbytes-small.nbytes;setattr(node,key,small)
                if not node.leaf:pack(node.left);pack(node.right)
            pack(inv.root);inv.bytes-=saved[0]
            record['inverse_saved_bytes']=saved[0]
            record['inverse_pack_action_relative_errors']=[float(la.norm(inv.apply(probe,solve=True,trans=i)-controls[i])/la.norm(controls[i])) for i in (0,1,2)]
            record['inverse_reachable_before_after']=[before,array_bytes(inv)]
            del probe,controls
        basis=SweepBasis(spec.get('batch',256));record['retained_factor_bytes']=fac.lu.nbytes if method=='dense' else fac.factor.bytes
    else:
        import native_pairs as pairs
        from hybrid_galerkin import NearOracle
        reference_pairs=NearOracle.pairs_values
        def native_near(self,i,j):
            saved=pairs.op._integrate_linear_pairs_box_sk_batched;pairs.install()
            try:return reference_pairs(self,i,j)
            finally:pairs.op._integrate_linear_pairs_box_sk_batched=saved
        NearOracle.pairs_values=native_near
        t=time.perf_counter()
        with packed_operator_blocks(True) as storage:
            h=PreconditionerOperator(oracle,coords,radius=support_radius(mesh,coords),tolerance=spec.get('op_tol',.01),budget=12*2**30)
        finish_operator(h,storage);stage('preconditioner_operator',t,**storage)
        rows,cols,_=h.equilibrate();t=time.perf_counter()
        inv=HMatrixSystem(h,coords,tolerance=spec.get('inv_tol',.01),budget=12*2**30,checkpoint=None)
        stage('inverse',t,bytes=inv.bytes)
        record['loose_operator_passes_production_gate']=h.production_gate_passed
        probe=np.random.default_rng(412).normal(size=(nd,2))+1j*np.random.default_rng(413).normal(size=(nd,2))
        controls=[inv.apply(probe,solve=True,trans=i) for i in (0,1,2)]
        ref=weakref.ref(h);inv.operator=None;del h;gc.collect();assert ref() is None
        assert all(np.array_equal(inv.apply(probe,solve=True,trans=i),controls[i]) for i in (0,1,2))
        record['construction_operator_released']=True
        if spec.get('pack_inverse'):
            saved=[0]
            def pack(node):
                for key in ('v12','v21','e1','e2'):
                    ar=getattr(node,key,None)
                    if ar is not None:
                        small=ar.astype(np.complex64)
                        assert np.isfinite(small).all() and not np.any((ar!=0)&(small==0))
                        saved[0]+=ar.nbytes-small.nbytes;setattr(node,key,small)
                if not node.leaf:pack(node.left);pack(node.right)
            pack(inv.root);inv.bytes-=saved[0]
            record['inverse_saved_bytes']=saved[0]
            record['inverse_pack_action_relative_errors']=[float(la.norm(inv.apply(probe,solve=True,trans=i)-controls[i])/la.norm(controls[i])) for i in (0,1,2)]
        del controls,probe
        record['retained_inverse_bytes']=array_bytes(inv)
        def pre_apply(v):pre_calls[0]+=1;return cols*inv.apply(rows*v,solve=True)
        pre=LinearOperator((nd,nd),matvec=pre_apply,dtype=complex)
        t=time.perf_counter();ex=MomentHybrid(mesh,k);inter=MomentHybrid(mesh,k*np.sqrt(eps));mass=sparse_mass(mesh)
        assert pairs.op._integrate_linear_pairs_box_sk_batched is pairs.original
        stage('fmm',t,bytes=ex.retained_bytes+inter.retained_bytes)
        factor=1/eps if pol=='TE' else 1.
        def apply(x):
            u,v=x[:n],x[n:]
            return np.concatenate((.5*(mass@u)+ex.apply(u,'K')+1j*k*ex.apply(u,'S')-inter.apply(v,'S'),ex.apply(u,'W')-1j*k*ex.apply(u,'KP')+.5j*k*(mass@u)+factor*(inter.apply(v,'KP')+.5*(mass@v))))
        def scaled_apply(v):a_calls[0]+=1;return apply(v/cols)/rows
        lin=LinearOperator((nd,nd),matvec=scaled_apply,dtype=complex)
        prev=None;outer=[]
    record['setup_seconds']=time.perf_counter()-started
    # 64 independent coefficient rows shared by all backends, plus both traces
    # at all geometric vertices. This is sampled equation validation, not mesh certification.
    sample=np.unique(np.r_[np.random.default_rng(2026111501).choice(nd,min(64,nd),False),np.arange(0,n,max(1,n//8)),n+np.arange(0,n,max(1,n//8))])
    t=time.perf_counter();exact,query=exact_rows(oracle,sample,nd);norms=np.sum(abs(exact),axis=1)
    stage('validation_row_setup',t,**query);record['sample_rows']=sample.tolist()
    field_times=[];solve_times=[];rhs_times=[];validation_times=[];io_times=[];mono=[];batch=spec.get('batch',256)
    for start in range(0,len(angles),batch):
        aa=angles[start:start+batch];t=time.perf_counter();b=dielectric.rhs_many(mesh,k,aa);rhs_times.append(time.perf_counter()-t)
        t=time.perf_counter()
        if method in ('dense','compressed'):
            x=sweep_solve(fac,b,basis,setting=spec.get('compression','auto'))
        else:
            mode=spec.get('krylov','cold');original_b=b;solve_angles=aa;recovery=None
            if mode=='rhs_qr':
                qrt=time.perf_counter();scaled=b/rows[:,None]
                q,recovery=_qr_basis(scaled,2e-15*la.norm(scaled))
                reconstruction_error=float(la.norm(scaled-q@recovery)/la.norm(scaled))
                assert reconstruction_error<1e-14
                record.setdefault('rhs_qr',[]).append(dict(columns=len(aa),rank=q.shape[1],seconds=time.perf_counter()-qrt,reconstruction_error=reconstruction_error))
                b=rows[:,None]*q;solve_angles=np.arange(b.shape[1]);del q,scaled
            if mode in ('batch_gmres','block_gmres'):
                if mode=='block_gmres':
                    from block_gmres import solve as batched_solve
                else:
                    from batched_gmres import solve as batched_solve
                x=np.empty_like(b);width=spec.get('krylov_batch',8)
                def am(v):return apply(v/cols[:,None])/rows[:,None]
                def pm(v):return cols[:,None]*inv.apply(rows[:,None]*v,solve=True)
                for first in range(0,b.shape[1],width):
                    options={'check_every':spec.get('true_check_every',1)} if mode=='block_gmres' else {}
                    y,details=batched_solve(am,pm,b[:,first:first+width]/rows[:,None],**options)
                    x[:,first:first+width]=y/cols[:,None]
                    record.setdefault('block_krylov',[]).append(dict(start=start+first,**details))
                    print(json.dumps(dict(stage='krylov_batch',start=start+first,**details)),file=sys.stderr,flush=True)
                solve_angles=[]
            else:x=np.empty_like(b)
            for j,angle in enumerate(solve_angles):
                ts=time.perf_counter();ac=a_calls[0];pc=pre_calls[0];history=[];mode=spec.get('krylov','cold')
                if mode in ('cold','warm','rhs_qr'):
                    y,status=gmres(lin,b[:,j]/rows,M=pre,x0=prev if mode=='warm' else None,rtol=1e-12,atol=0,restart=80,maxiter=10,callback=lambda r:history.append(float(r)),callback_type='pr_norm')
                else:
                    if mode=='lgmres_cold':outer=[]
                    y,status=lgmres(lin,b[:,j]/rows,M=pre,x0=prev if mode=='recycle' else None,rtol=1e-12,atol=0,inner_m=spec.get('inner_m',30),outer_k=8,maxiter=30,outer_v=outer,store_outer_Av=True,callback=lambda z:history.append(0))
                residual=lin@y-b[:,j]/rows;rel=float(la.norm(residual)/la.norm(b[:,j]/rows))
                assert status==0 and np.isfinite(y).all() and rel<=1.1e-12,(angle,status,rel)
                x[:,j]=y/cols;prev=y.copy()
                d=dict(angle=float(angle),seconds=time.perf_counter()-ts,iterations=len(history),iteration_semantics='inner' if mode in ('cold','warm','rhs_qr') else 'outer_callbacks',matvecs=a_calls[0]-ac,preconditioner_calls=pre_calls[0]-pc,status=int(status),scaled_relative_residual=rel,recycle_bytes=sum(a.nbytes for pair in outer for a in pair if isinstance(a,np.ndarray)))
                record['angles'].append(d)
                if (start+j)%30==0:print(json.dumps(dict(stage='angle',**d)),file=sys.stderr,flush=True)
            if recovery is not None:
                x=x@recovery;b=original_b
                # Check every original illumination with the accurate FMM, in addition
                # to independent exact coefficient rows below. No sampled RHS acceptance.
                reconstruction_residual=[]
                for j in range(len(aa)):
                    relative=float(la.norm(lin@(x[:,j]*cols)-b[:,j]/rows)/la.norm(b[:,j]/rows))
                    reconstruction_residual.append(relative)
                assert max(reconstruction_residual)<1.1e-12,reconstruction_residual
                record['rhs_qr'][-1]['max_original_scaled_relative_residual']=max(reconstruction_residual)
        solve_times.append(time.perf_counter()-t)
        t=time.perf_counter();field=op._farfield_linear_density_many(mesh,x[:n],k,aa,'DLP',projection='matched')+1j*k*op._farfield_linear_density_many(mesh,x[:n],k,aa,'SLP',projection='matched');field_times.append(time.perf_counter()-t)
        t=time.perf_counter();res=exact@x-b[sample];errors=np.max(abs(res)/(norms[:,None]*np.max(abs(x),axis=0)+abs(b[sample])),axis=0)
        assert np.isfinite(field).all() and np.isfinite(errors).all() and max(errors)<1e-12,errors
        validation_times.append(time.perf_counter()-t)
        record['batches'].append(dict(start=start,count=len(aa),peak_gib=rss(),max_exact_row_backward_error=float(max(errors)),rhs_bytes=b.nbytes,solution_bytes=x.nbytes))
        t=time.perf_counter();np.savez_compressed(str(out)+f'-batch{start:04d}.npz',angles=aa,field=field,density=x,rhs=b,rows=sample,residual=res,row_norm=norms);io_times.append(time.perf_counter()-t);mono.extend(field)
        del x,b,res
    record.update(rhs_seconds=sum(rhs_times),solve_seconds=sum(solve_times),field_seconds=sum(field_times),validation_seconds=sum(validation_times),archive_seconds=sum(io_times),peak_gib=rss(),wall_seconds=time.perf_counter()-started)
    if io_start:record['process_io_delta']={k:int(v)-io_start[k] for k,v in (line.split(':') for line in io_path.read_text().splitlines())}
    record['compute_seconds']=record['setup_seconds']+record['rhs_seconds']+record['solve_seconds']+record['field_seconds']
    if method in ('dense','compressed'):
        record['event']=fac.event
        if method=='dense':
            cleanup_start=time.perf_counter();fac.close();record['cleanup_seconds']=time.perf_counter()-cleanup_start
            if io_start:record['process_io_after_cleanup_delta']={k:int(v)-io_start[k] for k,v in (line.split(':') for line in io_path.read_text().splitlines())}
    else:record['pair_stats']=pairs.stats
    Path(str(out)+'.json').write_text(json.dumps(record,indent=2));print(json.dumps({k:v for k,v in record.items() if k not in ('angles','event','sample_rows')}),flush=True)

if __name__=='__main__':
    spec=json.loads(sys.argv[1]);state=CPUState(kernel_only=True);state.reuse_operators=False
    with _STATE.override(state),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1,'dense_residual_storage':spec.get('residual_storage','memory')}):main(spec)
