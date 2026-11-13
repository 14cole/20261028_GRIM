"""Small exact partition and storage-identity checks, independent of timing jobs."""
import sys,os,pathlib,json,numpy as np
sys.path.insert(0,os.environ.get('GRIM_ROOT','/workspace/grim-fmm-followup')+'/tools/GHOST')
from fmm_galerkin import circle_mesh
from hybrid_galerkin import HybridGalerkin,Cluster,partition
from ghost_backend.execution.options import cpu_allocation_scope,execution_scope
D=pathlib.Path(__file__).parent;out={}
with cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 mesh=circle_mesh(128,star=True,inward=True);a=HybridGalerkin(mesh,12-.2j,mode='stream');b=HybridGalerkin(mesh,12-.2j,mode='stream_sym');g=a.g
 membership=np.empty(len(a.points),int);membership[a.plan.order]=a.plan.leaf_of_point;membership=membership.reshape(-1,8)[:,0];panels=[np.flatnonzero(membership==i) for i in range(len(a.plan.leaf_start))];roots=[Cluster(p,g,12) for p in panels];mask=np.zeros((128,128),int);expected=np.zeros_like(mask)
 for i,js in enumerate(a.plan.leaf_neighbors):
  for j in js:
   expected[np.ix_(panels[i],panels[j])]=1
   for x,y,admissible in partition(roots[i],roots[j],1.5):mask[np.ix_(x.ids,y.ids)]+=1
 assert np.array_equal(mask,expected) and np.array_equal(mask,mask.T)
 out['partition_exact_once']=True;out['near_pairs']=int(mask.sum());out['K_KP_data_shared']=bool(np.shares_memory(a.corrections['K'].data,a.corrections['KP'].data));assert out['K_KP_data_shared']
 rng=np.random.default_rng(19);x=rng.normal(size=(128,3))+1j*rng.normal(size=(128,3));out['symmetric_storage_random_differences']={}
 for kind in ['S','K','KP','W']:
  u,v=a.apply(x,kind),b.apply(x,kind);error=float(np.max(abs(u-v))/np.max(abs(u)));out['symmetric_storage_random_differences'][kind]=error;assert error<1e-12
# Check a local nodal block against independently scattered panel coefficients.
 from hybrid_galerkin import NearOracle
 from nodal_block import NodalBlock
 oracle=NearOracle(mesh,12-.2j);pi=np.array([0,1,2,7,8,127]);pj=np.array([2,3,4,8,9,10]);block=NodalBlock(oracle,pi,pj);values=oracle.pairs_values(np.repeat(pi,len(pj)),np.tile(pj,len(pi)))
 for z in range(3):
  exact=np.zeros((128,128),complex)
  rr=np.repeat(g.node_ids[np.repeat(pi,len(pj))],2,axis=1).ravel();cc=np.tile(g.node_ids[np.tile(pj,len(pi))],(1,2)).ravel();np.add.at(exact,(rr,cc),values[z].ravel())
  rows=np.arange(len(block.rows))[::-2];cols=np.arange(len(block.cols))[1::2];actual=block.fetch(rows,cols)[z];truth=exact[np.ix_(block.rows[rows],block.cols[cols])];np.testing.assert_allclose(actual,truth,rtol=1e-13,atol=1e-25)
 out['nodal_block_reordered_subset_scatter']=True
(D/'PARTITION_CHECK.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
