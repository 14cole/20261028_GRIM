"""Audit-only local/coarse preconditioners over the existing global H operator.

Synthetic RHS experiment, not a production backend or certified field solver.
"""
import gc
import time
import warnings
import numpy as np
import scipy.linalg as la
from scipy.sparse.linalg import LinearOperator,gmres
from study import geometry,save


def execute(case,directory):
    from ghost_backend.twod import solver as s
    from ghost_backend.compressed import hmatrix as H
    from ghost_backend.compressed.hmatrix_factor import HMatrixFactor
    from ghost_backend.compressed.coefficients import NativeOracle
    from ghost_backend.compressed.runtime import coordinates
    from ghost_backend.execution.options import execution_scope,validate_options
    snapshot=geometry('inlet_high_contrast')
    snapshot['segments'][0]['properties'][1]='128'
    frequency=1.;k0=2*np.pi*frequency*1e9/s.C0
    material=s.MaterialLibrary.from_entries([],snapshot['dielectrics'],base_dir='.')
    options=validate_options(dict(factorization='compressed',mesh_strategy='global',basis_order=2,
        mesh_grading=False,enforce_mesh_density=False,assembly_threads=4,blas_threads=4,ram_budget_gib=12))
    report=dict(case=case,status='completed',scope='Fixed mesh synthetic RHS; no mesh-converged physical capacity claim.',
        restart=40,max_iterations_per_rhs=400,pols=[])
    with execution_scope(options):
        panels=s._build_panels(snapshot,.0254,s._mesh_wavelength_for_snapshot(snapshot,material,frequency)[0])
        infos=s._build_coupled_panel_info(panels,material,frequency,'TE',k0)
        mesh,_=s._build_linear_mesh_interface_aware(panels,infos)
        for pol in ('TE','TM'):
            infos=s._build_linear_coupled_infos(mesh,material,frequency,pol,k0)
            oracle=NativeOracle(mesh,infos,pol,k0,'dielectric')
            xy=coordinates(mesh,oracle.n); started=time.perf_counter()
            op=H.HMatrixOperator(oracle,xy,H.support_radius(mesh,xy),budget=4*1024**3)
            assembly=time.perf_counter()-started
            rng=np.random.default_rng(20261029); b=rng.standard_normal((oracle.n,2))+1j*rng.standard_normal((oracle.n,2))
            started=time.perf_counter();factor=HMatrixFactor(op,storage_budget_bytes=4*1024**3)
            reference=factor.solve(b);reference_seconds=time.perf_counter()-started;inverse_bytes=factor.factor.bytes
            del factor;gc.collect()
            row=dict(polarization=pol,unknowns=oracle.n,operator_bytes=op.bytes,operator_seconds=assembly,
                     reference_inverse_bytes=inverse_bytes,reference_build_solve_seconds=reference_seconds,schemes=[])
            for width,coarse in [(128,False),(512,False),(128,True)]:
                started=time.perf_counter();blocks=[];payload=0
                for start in range(0,op.n,width):
                    ids=op.order[start:start+width]
                    with warnings.catch_warnings():
                        warnings.simplefilter('error',la.LinAlgWarning)
                        lu,piv=la.lu_factor(op.get(ids,ids))
                    blocks.append((ids,lu,piv));payload+=ids.nbytes+lu.nbytes+piv.nbytes
                def local(v):
                    out=np.empty_like(v)
                    for ids,lu,piv in blocks:out[ids]=la.lu_solve((lu,piv),v[ids])
                    return out
                q=coarse_lu=coarse_piv=None
                if coarse:
                    columns=[]
                    for ids,_,_ in blocks:
                        for mask in (ids<len(mesh.nodes),ids>=len(mesh.nodes)):
                            group=ids[mask]
                            if len(group):
                                v=np.zeros(op.n,complex);v[group]=1/np.sqrt(len(group));columns.append(v)
                    q=np.column_stack(columns);del columns
                    coarse_matrix=q.conj().T@op.matmul(q)
                    coarse_lu,coarse_piv=la.lu_factor(coarse_matrix);del coarse_matrix
                    payload+=q.nbytes+coarse_lu.nbytes+coarse_piv.nbytes
                def apply(v):
                    out=local(v)
                    if coarse:out+=q@la.lu_solve((coarse_lu,coarse_piv),q.conj().T@(v-op.matmul(out)))
                    return out
                build_seconds=time.perf_counter()-started
                a=LinearOperator((op.n,op.n),matvec=op.matmul,dtype=complex)
                m=LinearOperator(a.shape,matvec=apply,dtype=complex)
                x=np.empty_like(b);details=[];started=time.perf_counter()
                for j in range(b.shape[1]):
                    iterations=[]
                    x[:,j],info=gmres(a,b[:,j],M=m,restart=40,maxiter=10,rtol=1e-11,atol=0,
                                      callback=lambda value:iterations.append(float(value)),callback_type='pr_norm')
                    details.append(dict(info=int(info),iterations=len(iterations)))
                solve_seconds=time.perf_counter()-started
                # Independent full-row oracle evaluation, not only the H product.
                residual=np.zeros(b.shape[1]);norm=0.
                for start in range(0,op.n,64):
                    ids=np.arange(start,min(start+64,op.n))
                    exact,tail=oracle.get_with_error(ids,np.arange(op.n))
                    norm=max(norm,float(np.max(np.sum(abs(exact),axis=1))))
                    residual=np.maximum(residual,np.max(abs(exact@x-b[ids])+tail@abs(x),axis=0))
                error=float(np.max(residual/(norm*np.max(abs(x),axis=0)+np.max(abs(b),axis=0))))
                difference=float(np.max(abs(x-reference))/max(float(np.max(abs(reference))),1e-300))
                scheme=dict(block_width=width,coarse=coarse,payload_bytes=payload,build_seconds=build_seconds,
                    solve_seconds=solve_seconds,rhs=details,full_row_backward_error=error,
                    normalized_solution_difference=difference,
                    passed=all(d['info']==0 for d in details) and error<=1e-12 and difference<=1e-8,
                    minimum_krylov_basis_bytes=16*op.n*41)
                row['schemes'].append(scheme)
                save(directory/'prototype_progress.json',dict(report,current=row))
                print(pol,width,coarse,scheme,flush=True)
                del blocks,q,coarse_lu,coarse_piv,a,m,x;gc.collect()
            report['pols'].append(row);save(directory/'prototype_progress.json',report)
            del op,oracle,reference,b;gc.collect()
    return report
