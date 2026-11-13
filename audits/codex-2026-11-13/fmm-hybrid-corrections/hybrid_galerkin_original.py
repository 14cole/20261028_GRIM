"""Research-only exact panel-pair partition with streamed or hierarchical near storage.
Reuses production cross_approximation, not the production global factorization.
No full near matrix is formed by the hybrid. All singular blocks stay dense.
"""
import time,numpy as np
from scipy.sparse import coo_matrix,csr_matrix
from cached_galerkin import CachedGalerkin
from cached_fmm import HelmholtzFMM

class NearOracle:
 def __init__(self,mesh,k,order=8):
  from ghost_backend.twod.assembly.geometry_plan import AssemblyGeometry
  self.mesh=mesh;self.k=k;self.order=order;self.g=AssemblyGeometry(mesh);self.pairs=0;self.seconds=0.
 def pairs_values(self,i,j):
  from ghost_backend.twod import operators as op
  g=self.g;t=time.perf_counter();out=[]
  for a in range(0,len(i),512):
   u,v=i[a:a+512],j[a:a+512]
   s,d=op._near_pair_blocks(self.mesh.elements,u,v,self.k,False,self.order,self.order,True,True,g.p0,g.segments,g.centers,g.lengths,g.node_ids,None,prepared_geometry=(g.p0,g.p0+g.segments,g.segments,g.lengths,g.normals))
   w=-self.k**2*np.einsum('bi,bi->b',g.normals[u],g.normals[v])[:,None,None]*s+np.outer([-1.,1.],[-1.,1.])[None]*s.sum(axis=(1,2))[:,None,None]/(g.lengths[u]*g.lengths[v])[:,None,None]
   out.append(np.stack([s,d,w]))
  self.pairs+=len(i);self.seconds+=time.perf_counter()-t
  return np.concatenate(out,axis=1) if out else np.empty((3,0,2,2),complex)
 def block(self,panels_i,panels_j,rows=None,cols=None):
  rows=np.arange(2*len(panels_i)) if rows is None else np.asarray(rows);cols=np.arange(2*len(panels_j)) if cols is None else np.asarray(cols)
  ri,rinv=np.unique(rows//2,return_inverse=True);cj,cinv=np.unique(cols//2,return_inverse=True)
  values=self.pairs_values(np.repeat(panels_i[ri],len(cj)),np.tile(panels_j[cj],len(ri))).reshape(3,len(ri),len(cj),2,2)
  return [v[rinv[:,None],cinv[None,:],rows[:,None]%2,cols[None,:]%2] for v in values]

class Cluster:
 def __init__(self,ids,g,leaf=24):
  self.ids=np.asarray(ids);p=np.concatenate([g.p0[ids],g.p0[ids]+g.segments[ids]]);self.lo=p.min(0);self.hi=p.max(0);self.diam=float(np.linalg.norm(self.hi-self.lo));self.children=[]
  if len(ids)>leaf:
   axis=np.argmax(np.ptp(g.centers[ids],axis=0));order=np.argsort(g.centers[ids,axis],kind='stable');mid=len(ids)//2
   self.children=[Cluster(ids[order[:mid]],g,leaf),Cluster(ids[order[mid:]],g,leaf)]

def partition(a,b,eta):
 gap=np.maximum(0,np.maximum(a.lo-b.hi,b.lo-a.hi));dist=float(np.linalg.norm(gap))
 if dist>0 and max(a.diam,b.diam)<=eta*dist:yield a,b,True
 elif not a.children and not b.children:yield a,b,False
 elif a.children and (not b.children or a.diam>=b.diam):
  for x in a.children:yield from partition(x,b,eta)
 else:
  for x in b.children:yield from partition(a,x,eta)

class HierarchicalNear:
 def __init__(self,oracle,panels,neighbors,tol=1e-11,leaf=24,eta=1.5,nodal=False):
  from ghost_backend.compressed.hmatrix import cross_approximation,HMatrixRejected
  t=time.perf_counter();g=oracle.g;roots=[Cluster(p,g,leaf) for p in panels];self.blocks=[];self.n=len(oracle.mesh.nodes);self.ranks=[];self.failures=0;self.estimated_max_ratio=0.;covered=0;self.dense_pairs=0;self.compressed_pairs=0
  rng=np.random.default_rng(20261113)
  for i,js in enumerate(neighbors):
   for j in js:
    for a,b,admissible in partition(roots[i],roots[j],eta):
     if nodal:
      from nodal_block import NodalBlock
      nodeblock=NodalBlock(oracle,a.ids,b.ids);rowids,colids=nodeblock.rows,nodeblock.cols;fetch=nodeblock.fetch
     else:
      rowids,colids=g.node_ids[a.ids].ravel(),g.node_ids[b.ids].ravel();fetch=lambda rows=None,cols=None:oracle.block(a.ids,b.ids,rows,cols)
     m,n=len(rowids),len(colids);covered+=len(a.ids)*len(b.ids)
     factors=None
     if admissible and min(m,n)>=32:
      sample=np.unique(np.linspace(0,m-1,min(8,m),dtype=int));v=fetch(sample,None);scales=[max(np.linalg.norm(x)*np.sqrt(m/len(sample)),1e-300) for x in v]
      try:
       factors,estimate=cross_approximation(lambda r:fetch(r,None),lambda c:fetch(None,c),(m,n),[tol*s for s in scales],8,rng,max_rank=max(1,min(m,n)//2))
       self.estimated_max_ratio=max(self.estimated_max_ratio,float(estimate))
       if sum(u.size+v.size for u,v in factors)>=3*m*n:factors=None
      except HMatrixRejected:self.failures+=1
     if factors is None:
      factors=[(x,None) for x in fetch()];self.dense_pairs+=len(a.ids)*len(b.ids)
     else:self.compressed_pairs+=len(a.ids)*len(b.ids);self.ranks.extend(u.shape[1] for u,v in factors)
     self.blocks.append((rowids,colids,factors))
  self.covered_pairs=covered;self.bytes=sum(r.nbytes+c.nbytes+sum(u.nbytes+(0 if v is None else v.nbytes) for u,v in f) for r,c,f in self.blocks);self.seconds=time.perf_counter()-t
 def apply(self,x,kind):
  out=np.zeros((self.n,x.shape[1]),complex);idx={'S':0,'K':1,'KP':1,'W':2}[kind]
  for r,c,f in self.blocks:
   u,v=f[idx]
   if kind=='KP':val=u.T@x[r] if v is None else v.T@(u.T@x[r]);np.add.at(out,c,val)
   else:val=u@x[c] if v is None else u@(v@x[c]);np.add.at(out,r,val)
  return out

class SymmetricCSR:
 """Complex symmetric, NOT Hermitian. Store the lower triangle only."""
 def __init__(self,lower):self.lower=lower;self.diagonal=lower.diagonal()
 def __matmul__(self,x):return self.lower@x+self.lower.T@x-self.diagonal[:,None]*x
 @property
 def nbytes(self):return self.lower.data.nbytes+self.lower.indices.nbytes+self.lower.indptr.nbytes+self.diagonal.nbytes

class HybridGalerkin(CachedGalerkin):
 def __init__(self,mesh,k,mode='hybrid',order=8,digits=10,separation=2,tol=1e-11,leaf=24,eta=1.5,row_batch=64):
  started=time.perf_counter();self.mesh=mesh;self.n=len(mesh.nodes);self.k=k;self.calls=0;self.fmm_seconds=0.;self.mode=mode;oracle=NearOracle(mesh,k,order);g=self.g=oracle.g
  if g.node_ids.shape[1]!=2:raise ValueError('P1 only')
  q,w=np.polynomial.legendre.leggauss(order);q=(q+1)/2;w=w/2;phi=np.column_stack((1-q,q));self.points=(g.p0[:,None]+q[None,:,None]*g.segments[:,None]).reshape(-1,2);self.normals=np.repeat(g.normals,order,axis=0)
  rr=np.repeat(np.arange(len(self.points)),2);cc=np.repeat(g.node_ids[:,None,:],order,axis=1).reshape(-1)
  self.Q=coo_matrix(((g.lengths[:,None,None]*w[None,:,None]*phi[None]).reshape(-1),(rr,cc)),shape=(len(self.points),self.n)).tocsr()
  self.D=coo_matrix((np.broadcast_to(w[None,:,None]*np.array([-1.,1.])[None,None,:],(len(g.lengths),order,2)).reshape(-1),(rr,cc)),shape=self.Q.shape).tocsr()
  self.plan=HelmholtzFMM(self.points,self.normals,complex(k).conjugate(),digits=digits,leaf_wavelengths=1.5,separation=separation,tile_points=256,gradients=True,near_storage=False,partition_points=np.repeat(g.centers,order,axis=0),support_radius=max(g.lengths)/2)
  if max(g.lengths)>.2*self.plan.side[-1]:raise ValueError('Panel too long')
  membership=np.empty(len(self.points),int);membership[self.plan.order]=self.plan.leaf_of_point;membership=membership.reshape(-1,order);assert np.all(membership==membership[:,:1]);membership=membership[:,0]
  panels=[np.flatnonzero(membership==i) for i in range(len(self.plan.leaf_start))];neighbors=self.plan.leaf_neighbors;self.near_pairs=sum(len(panels[i])*sum(len(panels[j]) for j in js) for i,js in enumerate(neighbors));near_start=time.perf_counter()
  if mode in ['hybrid','hybrid_nodal']:
   self.near=HierarchicalNear(oracle,panels,neighbors,tol,leaf,eta,nodal=mode=='hybrid_nodal');assert self.near.covered_pairs==self.near_pairs;near_bytes=self.near.bytes
  elif mode in ['stream','stream_sym']:
   # Build final nodal CSR rows in bounded chunks, merging panel duplicates locally.
   data=[bytearray() for _ in range(3)];indices=[bytearray() for _ in range(3)];ptr=[np.zeros(self.n+1,dtype=np.int64) for _ in range(3)];offset=[0]*3
   for a in range(0,self.n,row_batch):
    b=min(self.n,a+row_batch);ip=np.flatnonzero(np.any((g.node_ids>=a)&(g.node_ids<b),axis=1));pi=[];pj=[]
    for i in ip:
     j=np.concatenate([panels[v] for v in neighbors[membership[i]]]);pi.append(np.full(len(j),i));pj.append(j)
    pi=np.concatenate(pi);pj=np.concatenate(pj);v=oracle.pairs_values(pi,pj);r=np.repeat(g.node_ids[pi],2,axis=1).ravel();c=np.tile(g.node_ids[pj],(1,2)).ravel();keep=(r>=a)&(r<b)
    for z in range(3):
     select=keep&((c<=r) if mode=='stream_sym' and z in [0,2] else True)
     csr=coo_matrix((v[z].ravel()[select],(r[select]-a,c[select])),shape=(b-a,self.n)).tocsr();data[z].extend(csr.data.tobytes());indices[z].extend(csr.indices.astype(np.int32,copy=False).tobytes());ptr[z][a+1:b+1]=csr.indptr[1:]+offset[z];offset[z]+=csr.nnz
   self.corrections={name:csr_matrix((np.frombuffer(data[z],complex),np.frombuffer(indices[z],np.int32),ptr[z]),shape=(self.n,self.n),copy=False) for z,name in enumerate(['S','K','W'])};self.corrections['KP']=self.corrections['K'].T
   near_bytes=sum(m.data.nbytes+m.indices.nbytes+m.indptr.nbytes for m in [self.corrections[x] for x in ['S','K','W']])
   if mode=='stream_sym':
    for key in ['S','W']:
     self.corrections[key]=SymmetricCSR(self.corrections[key]);near_bytes+=self.corrections[key].diagonal.nbytes
  else:raise ValueError(mode)
  self.near_seconds=time.perf_counter()-near_start;self.queried_pairs=oracle.pairs;self.kernel_seconds=oracle.seconds;self.near_bytes=near_bytes;self.retained_bytes=self.plan.bytes+sum(v.data.nbytes+v.indices.nbytes+v.indptr.nbytes for v in [self.Q,self.D])+near_bytes;self.setup_seconds=time.perf_counter()-started
 def apply(self,x,kind='S'):
  if self.mode in ['stream','stream_sym']:return super().apply(x,kind)
  # Reuse the unchanged far evaluator; provide the hierarchical local action.
  class Action:
   def __init__(self,near,kind):self.near=near;self.kind=kind
   def __matmul__(self,x):return self.near.apply(x,self.kind)
  self.corrections={k:Action(self.near,k) for k in ['S','K','KP','W']}
  return super().apply(x,kind)
