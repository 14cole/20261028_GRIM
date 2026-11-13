"""Bounded complete-matrix reproduction plus worst-entry near/far evidence."""
import sys,pathlib,time,json,resource,numpy as np
from geometry_cases import CASES,mesh_from_loops,op,cpu_allocation_scope,execution_scope,CachedGalerkin
D=pathlib.Path(__file__).parent;name=sys.argv[2];build,k=CASES[name];mesh=mesh_from_loops(build());n=len(mesh.nodes);results={};start=time.perf_counter()
with cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 g=CachedGalerkin(mesh,k);identity=np.eye(n,dtype=complex);ids=np.arange(n)
 for kind in ['S','K','KP','W']:
  if kind=='W':ref=op._assemble_linear_hypersingular_matrix(mesh,k,output_node_ids=(ids,ids)).values
  else:
   s,d=op._assemble_linear_operator_matrices_multi(mesh,k,kind=='KP',[None],compute_single_layer=kind=='S',compute_double_layer=kind!='S',output_node_ids_many=[(ids,ids)])[0];ref=(s if kind=='S' else d).values
  y=np.concatenate([g.apply(identity[:,i:i+48],kind) for i in range(0,n,48)],axis=1);delta=abs(y-ref);flat=np.argpartition(delta.ravel(),-20)[-20:];flat=flat[np.argsort(delta.ravel()[flat])[::-1]];rr,cc=np.unravel_index(flat,delta.shape);near=np.asarray(g.corrections[kind][rr,cc]).ravel();norm=float(np.max(abs(ref)));selected=np.unique(cc)
  np.savez_compressed(D/(name+'-'+kind+'.npz'),reference_columns=ref[:,selected],actual_columns=y[:,selected],columns=selected,worst_rows=rr,worst_columns=cc,worst_reference=ref[rr,cc],worst_actual=y[rr,cc],worst_near=near)
  results[kind]=dict(relative_max_error=float(delta.max()/norm),reference_max=norm,worst_row=int(rr[0]),worst_col=int(cc[0]),worst_absolute_error=float(delta[rr[0],cc[0]]),worst_far_contribution=float(abs(y[rr[0],cc[0]]-near[0])))
  del ref,y,delta
print(json.dumps(dict(case=name,n=n,k=[k.real,k.imag],full_matrix=True,results=results,setup_seconds=g.setup_seconds,near_pairs=g.near_pairs,low_frequency_direct=g.plan.low_frequency_direct,levels=g.plan.levels,leaf_wavelengths=float(g.plan.side[-1]*abs(k)/(2*np.pi)),elapsed=time.perf_counter()-start,peak_rss_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2)))
