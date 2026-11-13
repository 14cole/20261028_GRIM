"""Audit-only reusable FMM with panel-based near field and P1 Galerkin testing.
Quadrature nodes from one panel share a leaf. Native Galerkin integration
replaces the entire near field, eliminating stored point-neighbor matrices.
"""
import numpy as np,time
from scipy.sparse import coo_matrix
from cached_fmm import HelmholtzFMM
class CachedGalerkin:
 def __init__(self,mesh,k,order=8,digits=10,separation=2,tile_points=256):
  from ghost_backend.twod import operators as op
  from ghost_backend.twod.assembly.geometry_plan import AssemblyGeometry
  started=time.perf_counter();self.mesh=mesh;self.n=len(mesh.nodes);self.k=k;self.calls=0;self.fmm_seconds=0.;g=AssemblyGeometry(mesh);self.g=g
  if g.node_ids.shape[1]!=2:raise ValueError('P1 only')
  q,w=np.polynomial.legendre.leggauss(order);q=(q+1)/2;w=w/2;phi=np.column_stack((1-q,q));self.points=(g.p0[:,None]+q[None,:,None]*g.segments[:,None]).reshape(-1,2);self.normals=np.repeat(g.normals,order,axis=0)
  rr=np.repeat(np.arange(len(self.points)),2);cc=np.repeat(g.node_ids[:,None,:],order,axis=1).reshape(-1)
  vals=(g.lengths[:,None,None]*w[None,:,None]*phi[None]).reshape(-1);self.Q=coo_matrix((vals,(rr,cc)),shape=(len(self.points),self.n)).tocsr()
  vals=np.broadcast_to(w[None,:,None]*np.array([-1.,1.])[None,None,:],(len(g.lengths),order,2)).reshape(-1);self.D=coo_matrix((vals,(rr,cc)),shape=self.Q.shape).tocsr()
  self.plan=HelmholtzFMM(self.points,self.normals,complex(k).conjugate(),digits=digits,leaf_wavelengths=1.5,separation=separation,tile_points=tile_points,gradients=True,near_storage=False,partition_points=np.repeat(g.centers,order,axis=0),support_radius=max(g.lengths)/2)
  if max(g.lengths)>.2*self.plan.side[-1]:raise ValueError('Panel too long for research box-support bound')
  leaf=np.empty(len(self.points),int);leaf[self.plan.order]=self.plan.leaf_of_point;leaf=leaf.reshape(-1,order);assert np.all(leaf==leaf[:,:1]);leaf=leaf[:,0]
  panels=[np.flatnonzero(leaf==i) for i in range(len(self.plan.leaf_start))];counts=[len(a)*sum(len(panels[j]) for j in ns) for a,ns in zip(panels,self.plan.leaf_neighbors)];count=sum(counts);self.near_pairs=count
  # Bound all coefficient-building buffers before allocating them.
  if count*4*(8*2+16*3)>2*2**30:raise MemoryError('Research panel-near construction budget exceeded')
  pi=np.empty(count,int);pj=np.empty(count,int);offset=0
  for a,ns in zip(panels,self.plan.leaf_neighbors):
   b=np.concatenate([panels[j] for j in ns]);size=len(a)*len(b);pi[offset:offset+size]=np.repeat(a,len(b));pj[offset:offset+size]=np.tile(b,len(a));offset+=size
  row=np.repeat(g.node_ids[pi],2,axis=1).reshape(-1);col=np.tile(g.node_ids[pj],(1,2)).reshape(-1);sv=np.empty((count,2,2),complex);kv=np.empty_like(sv);wv=np.empty_like(sv);outer=np.outer([-1.,1.],[-1.,1.]);near_start=time.perf_counter()
  for start in range(0,count,512):
   sl=slice(start,start+512);i,j=pi[sl],pj[sl]
   S,K=op._near_pair_blocks(mesh.elements,i,j,k,False,order,order,True,True,g.p0,g.segments,g.centers,g.lengths,g.node_ids,None,prepared_geometry=(g.p0,g.p0+g.segments,g.segments,g.lengths,g.normals))
   sv[sl]=S;kv[sl]=K;ndot=np.einsum('bi,bi->b',g.normals[i],g.normals[j]);wv[sl]=-k*k*ndot[:,None,None]*S+outer[None]*S.sum(axis=(1,2))[:,None,None]/(g.lengths[i]*g.lengths[j])[:,None,None]
  self.corrections={kind:coo_matrix((v.reshape(-1),(row,col)),shape=(self.n,self.n)).tocsr() for kind,v in [('S',sv),('K',kv),('W',wv)]};self.corrections['KP']=self.corrections['K'].T.tocsr();self.near_seconds=time.perf_counter()-near_start
  self.retained_bytes=self.plan.bytes+sum(v.data.nbytes+v.indices.nbytes+v.indptr.nbytes for v in [self.Q,self.D,*self.corrections.values()]);self.setup_seconds=time.perf_counter()-started
 def evaluate(self,charges=None,dipoles=None,gradient=False):
  result=self.plan.apply(None if charges is None else charges.conj(),None if dipoles is None else dipoles.conj(),gradient=gradient)
  if gradient:return tuple(-a.conj() for a in result)
  return -result.conj()
 def apply(self,x,kind='S'):
  x=np.asarray(x);vector=x.ndim==1
  if vector:x=x[:,None]
  rhs=self.Q@x;start=time.perf_counter()
  if kind=='S':y=self.Q.T@self.evaluate(charges=rhs)
  elif kind=='K':y=self.Q.T@self.evaluate(dipoles=rhs)
  elif kind=='KP':_,grad=self.evaluate(charges=rhs,gradient=True);y=self.Q.T@np.einsum('nib,ni->nb',grad,self.normals)
  elif kind=='W':
   v=self.evaluate(charges=np.concatenate([self.D@x,rhs*self.normals[:,0,None],rhs*self.normals[:,1,None]],axis=1));a,b,c=np.split(v,3,axis=1);y=self.D.T@a-self.k**2*(self.Q.T@(b*self.normals[:,0,None]+c*self.normals[:,1,None]))
  else:raise ValueError(kind)
  self.calls+=1;self.fmm_seconds+=time.perf_counter()-start;y+=self.corrections[kind]@x
  return y[:,0] if vector else y
