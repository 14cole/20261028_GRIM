"""Fresh allocation and compensated-factor diagnostics, independent of builder runs."""
import os,sys,json,tracemalloc
from pathlib import Path
import numpy as np
import scipy.linalg as la
sys.path.insert(0,str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST'))
from ghost_backend.linalg.hierarchical import Node
from codex_hooks import convert
from rank_guard import convert_factor
rng=np.random.default_rng(20261116)
def random(shape):return rng.normal(size=shape)+1j*rng.normal(size=shape)
node=Node();node.leaf=False;node.n=1024
for key in ('left','right'):
    child=Node();child.leaf=True;child.n=512
    child.lu=la.lu_factor(np.eye(512,dtype=complex));setattr(node,key,child)
node.e1=random((512,64))*.001;node.e2=random((512,64))*.001
node.v12=random((64,512))*.001;node.v21=random((64,512))*.001
correction=np.eye(128,dtype=complex);correction[:64,64:]=node.v12@node.e2;correction[64:,:64]=node.v21@node.e1
node.lu=la.lu_factor(correction)
b=random((1024,512));reference=node.solve(b);work=b.copy()
tracemalloc.start();tracemalloc.reset_peak();node.solve_into(work,work)
current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
assert np.array_equal(work,reference)
assert peak>1024**2 and peak<8*b.nbytes+1024**2
out=dict(aliased_node_solve=dict(rhs_bytes=b.nbytes,tracked_peak_scratch_bytes=peak,
    claude_allowance_bytes=1024**2,corrected_allowance_bytes=8*b.nbytes+1024**2,bit_identical=True),rank_checks=[])
for key in ('e1','v12'):
    u=random((50,4));v=random((4,50));d=np.array([1.,1e-20,1e-40,1e-50])
    if key=='e1':a=u*d;partner=v/d[:,None];product=lambda x:x@partner
    else:a=v*d[:,None];partner=u/d;product=lambda x:partner@x
    plain,_=convert(a);checked,rec=convert_factor(a,key);truth=product(a)
    error=lambda x:float(la.norm(product(x.astype(complex))-truth)/la.norm(truth))
    assert plain.dtype==np.complex64 and checked is a and error(plain)>.1 and error(checked)==0
    out['rank_checks'].append(dict(key=key,global_guard_product_error=error(plain),rank_guard_product_error=error(checked),record=rec))
for key in ('e1','v12'):
    for a in (np.zeros((0,4),complex),np.zeros((4,0),complex),np.asfortranarray(random((16,8))),random((32,8))[::2]):
        result,_=convert_factor(a,key);assert result.dtype==np.complex64
Path(__file__).with_name('scratch-guard-check.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
