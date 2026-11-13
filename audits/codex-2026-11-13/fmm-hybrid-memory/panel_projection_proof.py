"""Storage accounting and algebraic proof for a proposed panel-moment far adapter.
This does NOT implement a new full operator or measure a projected solver peak.
"""
import os,sys,pathlib,json,numpy as np
sys.path.insert(0,os.environ.get('GRIM_ROOT','/workspace/grim-fmm-followup')+'/tools/GHOST')
from fmm_galerkin import circle_mesh
from ghost_backend.twod.assembly.geometry_plan import AssemblyGeometry
from cached_fmm import HelmholtzFMM
D=pathlib.Path(__file__).parent;records=[]
for kval in [40+0j,40-.8j,12+0j]:
 n=4096;mesh=circle_mesh(n,star=True,inward=True);g=AssemblyGeometry(mesh);q,w=np.polynomial.legendre.leggauss(8);q=(q+1)/2;w=w/2;phi=np.column_stack([1-q,q]);points=(g.p0[:,None]+q[None,:,None]*g.segments[:,None]).reshape(-1,2);normals=np.repeat(g.normals,8,axis=0)
 f=HelmholtzFMM(points,normals,kval.conjugate(),digits=10,leaf_wavelengths=1.5,separation=2,tile_points=256,gradients=True,near_storage=False,partition_points=np.repeat(g.centers,8,axis=0),support_radius=max(g.lengths)/2)
 ids=f.order.reshape(-1,8);assert np.all(ids//8==ids[:,:1]//8);panels=ids[:,0]//8;nodes=g.node_ids[panels];length=g.lengths[panels];width=f.Q[-1];e=f.E.reshape(n,8,width);eo=f.Eout.reshape(n,8,width);dip=f.dip.reshape(n,8,width);assert np.all(dip==dip[:,:1,:])
 source=np.einsum('pqv,qa,p,q->pav',e,phi,length,w);target=np.einsum('pqv,qa,p,q->pav',eo,phi,length,w);rng=np.random.default_rng(20261113);x=rng.normal(size=(n,3))+1j*rng.normal(size=(n,3));nodal=x[nodes];weighted=np.einsum('qa,pab->pqb',phi,nodal)*length[:,None,None]*w[None,:,None];errors={}
 def compare(name,a,b):
  error=float(np.max(abs(a-b))/max(np.max(abs(a)),1e-300));errors[name]=error;assert error<5e-13,(name,error)
 direct=np.einsum('pqv,pqb->pvb',e,weighted);projected=np.einsum('pav,pab->pvb',source,nodal);compare('source_charge',direct,projected)
 compare('source_dipole',np.einsum('pqv,pqb->pvb',e*dip,weighted),projected*dip[:,0,:,None])
 derivative=(nodal[:,1]-nodal[:,0])[:,None,:]*w[None,:,None];compare('source_derivative',np.einsum('pqv,pqb->pvb',e,derivative),(source.sum(axis=1)/length[:,None])[:,:,None]*(nodal[:,1]-nodal[:,0])[:,None,:])
 leaf=f.leaf_of_point.reshape(n,8)[:,0];lc=rng.normal(size=(len(f.leaf_start),width,3))+1j*rng.normal(size=(len(f.leaf_start),width,3));local=lc[leaf]
 for label,factor in [('value',np.ones((n,width))),('normal_gradient',-dip[:,0])]:
  point=np.einsum('pqv,pvb->pqb',eo,local*factor[:,:,None]);direct=np.einsum('qa,pqb,p,q->pab',phi,point,length,w);projected=np.einsum('pav,pvb->pab',target,local*factor[:,:,None]);a=np.zeros((n,3),complex);b=np.zeros_like(a);np.add.at(a,nodes.ravel(),direct.reshape(-1,3));np.add.at(b,nodes.ravel(),projected.reshape(-1,3));compare('target_'+label,a,b)
 point=np.einsum('pqv,pvb->pqb',eo,local);compare('target_derivative',np.einsum('q,pqb->pb',w,point),(target.sum(axis=1)/length[:,None])[:,:,None].__mul__(local).sum(axis=1))
 if f.low_frequency_direct:assert np.max(abs(f.apply(np.ones((len(points),1),complex))))==0
 records.append(dict(n=n,k=[kval.real,kval.imag],plan_bytes=f.bytes,point_phase_bytes=f.E.nbytes+f.Eout.nbytes+f.dip.nbytes,proposed_source_target_projection_bytes=source.nbytes+target.nbytes,phase_payload_ratio=(f.E.nbytes+f.Eout.nbytes+f.dip.nbytes)/(source.nbytes+target.nbytes),leaf_expansion_directions=width,all_near=f.low_frequency_direct,translation_groups=sum(len(v) for v in f.m2l[2:]),relative_max_identity_errors=errors,full_operator_implemented=False,projected_peak_measured=False))
 del f,e,eo,dip,source,target,lc,local
(D/'PANEL_PROJECTION_PROOF.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps(records,indent=2))
