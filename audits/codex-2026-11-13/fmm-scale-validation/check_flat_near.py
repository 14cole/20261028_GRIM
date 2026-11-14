"""Exercise exact fallback in the real nodal near builder on collinear panels."""
import os,sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,os.environ['GRIM_ROOT']+'/tools/GHOST');sys.path.insert(0,'fmm')
from ghost_backend.twod.geometry import LinearNode,LinearElement,LinearMesh
from ghost_backend.execution.cpu import CPUState,_STATE
from ghost_backend.execution.options import cpu_allocation_scope,execution_scope
from hybrid_galerkin import NearOracle,HierarchicalNear
from nodal_block import NodalBlock
import safe_cross
records=[];arrays={}
with _STATE.override(CPUState(kernel_only=True)),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 for scale in [1e-6,1.,1e6]:
  nodes=[];elements=[];panels=[]
  for base in [0.,2.]:
   xy=np.c_[np.linspace(base,base+1,33)*scale,np.zeros(33)];offset=len(nodes);ids=[]
   nodes.extend(LinearNode(p,(offset+i,0)) for i,p in enumerate(xy))
   for i in range(32):
    p,q=xy[i:i+2];length=float(np.linalg.norm(q-p));t=(q-p)/length;idx=len(elements);ids.append(idx)
    elements.append(LinearElement('line',2,0,0,0,(offset+i,offset+i+1),p,q,(p+q)/2,t,np.array([-t[1],t[0]]),length,idx))
   panels.append(np.array(ids))
  mesh=LinearMesh(nodes,elements);oracle=NearOracle(mesh,(2.-.08j)/scale);before=safe_cross.UNSEEN_COMPONENTS['rejected_blocks']
  near=HierarchicalNear(oracle,panels,[[1],[0]],tol=1e-13,nodal=True)
  assert safe_cross.UNSEEN_COMPONENTS['rejected_blocks']-before==2 and len(near.blocks)==2
  for index,(rows,cols,factors) in enumerate(near.blocks):
   ref=NodalBlock(oracle,panels[index],panels[1-index]).fetch()
   for c,((u,v),expected) in enumerate(zip(factors,ref)):
    assert v is None and np.array_equal(u,expected)
    arrays[f'{scale}-{index}-{c}']=u
   assert np.count_nonzero(ref[1])==0
  records.append(dict(length_scale=scale,exact_rejected_blocks=2,bytes=near.bytes,bitwise_exact=True))
for scale in [1e-6,1e6]:
 for c,power in [(0,2),(2,0)]:
  ref=arrays[f'1.0-0-{c}'];got=arrays[f'{scale}-0-{c}']/scale**power
  assert np.linalg.norm(got-ref)/np.linalg.norm(ref)<1e-12
np.savez_compressed('results/flat-near.npz',**arrays)
Path('results/flat-near.json').write_text(json.dumps(records,indent=2))
