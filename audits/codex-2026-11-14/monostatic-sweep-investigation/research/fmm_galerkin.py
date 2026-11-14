"""Research-only P1 Galerkin S,K,K',W using native FMM plus exact near correction.
No production entry point or certification is provided by this module.
"""
import numpy as np,time
from scipy.sparse import coo_matrix
from scipy.spatial import cKDTree
from scipy.special import hankel2
def evaluate(*args, **kwargs):
 """Load the optional native library only for a native FMM product."""
 from fmm_native import evaluate as native_evaluate
 return native_evaluate(*args, **kwargs)

def circle_mesh(n,radius=1.,star=False,inward=False):
 from ghost_backend.twod.geometry import LinearNode,LinearElement,LinearMesh
 theta=(1 if inward else -1)*np.linspace(0,2*np.pi,n,endpoint=False);r=radius*(1+.2*np.cos(5*theta)) if star else np.full(n,radius)
 xy=np.column_stack((r*np.cos(theta),r*np.sin(theta)));nodes=[LinearNode(p,(i,0)) for i,p in enumerate(xy)];elements=[]
 for i,p in enumerate(xy):
  j=(i+1)%n;v=xy[j]-p;length=np.linalg.norm(v);t=v/length;normal=np.array([-t[1],t[0]])
  elements.append(LinearElement('body',2,0,0,0,(i,j),p,xy[j],(p+xy[j])/2,t,normal,length,i))
 return LinearMesh(nodes,elements)

class GalerkinFMM:
 def __init__(self,mesh,k,order=8,eps=1e-12,near_ratio=5.):
  from ghost_backend.twod import operators as op
  from ghost_backend.twod.assembly.geometry_plan import AssemblyGeometry
  started=time.perf_counter();self.mesh=mesh;self.n=len(mesh.nodes);self.k=k;self.eps=eps;self.calls=0;self.fmm_seconds=0.
  g=AssemblyGeometry(mesh);self.g=g;self.order=order;q,w=np.polynomial.legendre.leggauss(order);q=(q+1)/2;w=w/2;phi=np.column_stack((1-q,q))
  self.points=(g.p0[:,None,:]+q[None,:,None]*g.segments[:,None,:]).reshape(-1,2)
  self.normals=np.repeat(g.normals,order,axis=0);lengths=g.lengths
  rows=np.repeat(np.arange(len(self.points)),2);cols=np.repeat(g.node_ids[:,None,:],order,axis=1).reshape(-1)
  vals=(lengths[:,None,None]*w[None,:,None]*phi[None,:,:]).reshape(-1)
  self.Q=coo_matrix((vals,(rows,cols)),shape=(len(self.points),self.n)).tocsr()
  dvals=np.broadcast_to(w[None,:,None]*np.array([-1.,1.])[None,None,:],(len(lengths),order,2)).reshape(-1)
  self.D=coo_matrix((dvals,(rows,cols)),shape=self.Q.shape).tocsr()
  centers=g.centers;tree=cKDTree(centers);pairs=[]
  for i,p in enumerate(centers):
   for j in tree.query_ball_point(p,near_ratio*max(lengths)):
    if np.linalg.norm(p-centers[j])<=near_ratio*max(lengths[i],lengths[j]):pairs.append((i,j))
  pairs=np.asarray(pairs,dtype=np.int64);self.near_pairs=len(pairs);svals=[];kvals=[];wvals=[];rr=[];cc=[]
  for start in range(0,len(pairs),128):
   pi,pj=pairs[start:start+128].T
   exact_s,exact_k=op._near_pair_blocks(mesh.elements,pi,pj,k,False,order,order,True,True,g.p0,g.segments,g.centers,g.lengths,g.node_ids,None,prepared_geometry=(g.p0,g.p0+g.segments,g.segments,g.lengths,g.normals))
   x=self.points.reshape(-1,order,2)[pi];y=self.points.reshape(-1,order,2)[pj];delta=x[:,:,None,:]-y[:,None,:,:];dist=np.linalg.norm(delta,axis=-1);valid=dist>1e-14*max(float(np.max(lengths)),1e-300);safe=np.where(valid,dist,1.)
   green=np.where(valid,.25j*hankel2(0,k*safe),0);derivative=np.where(valid,.25j*k*hankel2(1,k*safe)/safe,0)*np.einsum('bqsi,bi->bqs',delta,g.normals[pj])
   weights=lengths[pi,None,None]*lengths[pj,None,None]*w[None,:,None]*w[None,None,:]
   raw_s=np.einsum('qi,bqs,sj->bij',phi,green*weights,phi);raw_k=np.einsum('qi,bqs,sj->bij',phi,derivative*weights,phi)
   delta_s=exact_s-raw_s;delta_k=exact_k-raw_k
   # Exact Maue correction from the same integrated S block and its sum.
   ndot=np.einsum('bi,bi->b',g.normals[pi],g.normals[pj]);outer=np.outer([-1.,1.],[-1.,1.])
   delta_w=-k*k*ndot[:,None,None]*delta_s+outer[None]*delta_s.sum(axis=(1,2))[:,None,None]/(lengths[pi]*lengths[pj])[:,None,None]
   rr.extend(np.repeat(g.node_ids[pi],2,axis=1).ravel());cc.extend(np.tile(g.node_ids[pj],(1,2)).ravel());svals.extend(delta_s.ravel());kvals.extend(delta_k.ravel());wvals.extend(delta_w.ravel())
  self.corrections={kind:coo_matrix((vals,(rr,cc)),shape=(self.n,self.n)).tocsr() for kind,vals in [('S',svals),('K',kvals),('W',wvals)]};self.corrections['KP']=self.corrections['K'].T.tocsr()
  arrays=[self.points,self.normals]
  self.retained_bytes=sum(a.nbytes for a in arrays)+sum(a.data.nbytes+a.indices.nbytes+a.indptr.nbytes for a in [self.Q,self.D,*self.corrections.values()]);self.setup_seconds=time.perf_counter()-started
 def apply(self,x,kind='S'):
  x=np.asarray(x);vector=x.ndim==1
  if vector:x=x[:,None]
  rhs=self.Q@x;start=time.perf_counter()
  if kind=='S':value=evaluate(self.points,self.k,charges=rhs.T,eps=self.eps)[0].T;y=self.Q.T@value
  elif kind=='K':value=evaluate(self.points,self.k,dipoles=rhs.T,normals=self.normals,eps=self.eps)[0].T;y=self.Q.T@value
  elif kind=='KP':grad=evaluate(self.points,self.k,charges=rhs.T,gradient=True,eps=self.eps)[1];y=self.Q.T@np.einsum('din,ni->nd',grad,self.normals)
  elif kind=='W':
   strengths=np.concatenate([(self.D@x).T,(rhs*self.normals[:,0,None]).T,(rhs*self.normals[:,1,None]).T],axis=0)
   value=evaluate(self.points,self.k,charges=strengths,eps=self.eps)[0].T;a,b,c=np.split(value,3,axis=1);y=self.D.T@a-self.k**2*(self.Q.T@(b*self.normals[:,0,None]+c*self.normals[:,1,None]))
  else:raise ValueError(kind)
  self.fmm_seconds+=time.perf_counter()-start;self.calls+=1;y+=self.corrections[kind]@x
  return y[:,0] if vector else y
