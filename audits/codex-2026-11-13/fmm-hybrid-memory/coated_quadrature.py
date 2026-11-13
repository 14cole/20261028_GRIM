"""Resolve worst thin-gap entries with joint/separate integration and independent Gauss rules."""
import pathlib,sys,json,time,numpy as np
from scipy.special import hankel2
from geometry_cases import circle,mesh_from_loops,op,cpu_allocation_scope,execution_scope
from ghost_backend.twod.assembly.geometry_plan import AssemblyGeometry
from ghost_backend.twod.assembly import thin_gap
D=pathlib.Path(__file__).parent;name='difficult-coated-512-stream';k=40-.8j;mesh=mesh_from_loops([circle(256,1.),circle(256,.999)]);g=AssemblyGeometry(mesh);out=[]
def aggregate(blocks,pairs,kind):
 value=0j
 for b,(i,j,ii,jj) in zip(blocks,pairs):
  if kind=='W':b=-k*k*np.dot(g.normals[i],g.normals[j])*b+np.outer([-1.,1.],[-1.,1.])*b.sum()/(g.lengths[i]*g.lengths[j])
  value+=b[ii,jj]
 return value
with cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 for kind in ['S','W']:
  raw=np.load(D/(name+'-'+kind+'.npz'));actual=raw['actual_matrix'] if 'actual_matrix' in raw else raw['actual_columns'];ref=raw['reference_rows'] if 'reference_rows' in raw else raw['reference_columns'];column_ids=np.arange(actual.shape[1]) if 'actual_matrix' in raw else raw['matrix_columns'];row,offset=map(int,np.unravel_index(np.argmax(abs(actual-ref)),actual.shape));col=int(column_ids[offset]);obs=np.argwhere(g.node_ids==row);src=np.argwhere(g.node_ids==col);pairs=[(int(i),int(j),int(ii),int(jj)) for i,ii in obs for j,jj in src];pi=np.array([p[0] for p in pairs]);pj=np.array([p[1] for p in pairs]);record=dict(operator=kind,row=row,col=col,pairs=pairs,thin_qualifies=op._thin_gap_mask([mesh.elements[i] for i in pi],[mesh.elements[j] for j in pj]).tolist());values={}
  for want_k,label in [(False,'S_only'),(True,'joint_SK')]:
   s,_=op._near_pair_blocks(mesh.elements,pi,pj,k,False,8,8,True,want_k,g.p0,g.segments,g.centers,g.lengths,g.node_ids,None,prepared_geometry=(g.p0,g.p0+g.segments,g.segments,g.lengths,g.normals));values[label]=aggregate(s,pairs,kind)
  # Tighten the ordinary dispatcher's tolerance, preserving its eligibility
  # tests: some selected pairs deliberately do NOT qualify as thin gaps.
  original_tol=op.NEAR_PAIR_QUADRATURE_RTOL
  try:
   for tol in [1e-9,1e-12,1e-14]:
    op.NEAR_PAIR_QUADRATURE_RTOL=tol
    try:
     sb,_=op._near_pair_blocks(mesh.elements,pi,pj,k,False,8,8,True,False,g.p0,g.segments,g.centers,g.lengths,g.node_ids,None,prepared_geometry=(g.p0,g.p0+g.segments,g.segments,g.lengths,g.normals));values['near_rtol_'+str(tol)]=aggregate(sb,pairs,kind)
    except Exception as exc:record.setdefault('tight_failures',{})[str(tol)]=str(exc)
  finally:op.NEAR_PAIR_QUADRATURE_RTOL=original_tol
  # Tensor Gauss uses raw Hankel kernels; it does not call GHOST quadrature.
  for order in [256,512,1024,2048]:
   q,w=np.polynomial.legendre.leggauss(order);q=(q+1)/2;w=w/2;phi=np.column_stack([1-q,q]);blocks=[]
   for i,j,ii,jj in pairs:
    x=g.p0[i]+q[:,None]*g.segments[i];y=g.p0[j]+q[:,None]*g.segments[j];distance=np.linalg.norm(x[:,None]-y[None],axis=-1);green=.25j*hankel2(0,k*distance);block=(phi*w[:,None]).T@green@(phi*w[:,None])*g.lengths[i]*g.lengths[j];blocks.append(block)
   values['independent_GL_'+str(order)]=aggregate(blocks,pairs,kind)
  values['matrix_reference']=complex(ref[row,offset]);values['streamed']=complex(actual[row,offset]);anchor=values['independent_GL_2048'];record['values']={key:[v.real,v.imag] for key,v in values.items()};record['absolute_difference_from_GL2048']={key:abs(v-anchor) for key,v in values.items()};out.append(record)
(D/'COATED_QUADRATURE.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
