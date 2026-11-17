"""Reviewer unit test of hmatrix_build._solve_in_place accounting (stub system, real function).
Written before reading Codex's test_build.py."""
import os,sys,json
from contextlib import contextmanager
from pathlib import Path
import numpy as np,scipy.linalg as la
sys.path.insert(0,str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST'))
from ghost_backend.compressed.hmatrix_build import _solve_in_place
class Steps:
    def __init__(self,owner):self.owner=owner;self.log=[]
    @contextmanager
    def step(self,label,additional,*live):
        self.log.append(dict(label=label,additional=int(additional),live_bytes=int(sum(a.nbytes for a in live)),retained=int(self.owner.bytes)));yield
class System:
    def __init__(self,budget):self.bytes=0;self.budget=budget;self.checks=[];self.construction=Steps(self)
    def check_storage(self,count):
        self.checks.append(int(count))
        if self.bytes+count>self.budget:raise MemoryError('cap')
    def reserve(self,count):self.check_storage(count);self.bytes+=count
class Child:
    def __init__(self,a):self.lu=la.lu_factor(a);self.a=a
    def solve_into(self,b,result,trans=0):result[...]=la.lu_solve(self.lu,b)
r=np.random.default_rng(4);n,k=40,6;A=r.standard_normal((n,n))+1j*r.standard_normal((n,n))+8*np.eye(n);child=Child(A);out=[]
def case(name,u,budget=10**9,live=()):
    s=System(budget);s.reserve(u.nbytes);ref=np.linalg.solve(A,np.asarray(u,complex));before=s.bytes;err=None;e=None
    try:e=_solve_in_place(s,child,u,*live)
    except MemoryError as ex:err='MemoryError'
    rec=dict(name=name,input=str(u.dtype),writeable=bool(u.flags.writeable),error=err,reserved_before=before,reserved_after=s.bytes,checks=s.checks[1:],steps=s.construction.log)
    if e is not None:
        rec.update(result_dtype=str(e.dtype),same_object_as_input=e is u,result_bytes=int(e.nbytes),reserved_equals_result_bytes=s.bytes==e.nbytes,
            rel_error=float(np.linalg.norm(e-ref)/np.linalg.norm(ref)),in_place_allowance_ok=s.construction.log[-1]['additional']==8*e.nbytes+2**20,
            copy_step_live_or_additional_covers_copy=(len(s.construction.log)==1 or s.construction.log[0]['additional']>=e.nbytes),
            second_step_counts_copy_as_live=(len(s.construction.log)==1 or s.construction.log[-1]['live_bytes']>=e.nbytes+sum(a.nbytes for a in live)))
    out.append(rec);print({k_:v for k_,v in rec.items() if k_!='steps'});return rec
c128=r.standard_normal((n,k))+1j*r.standard_normal((n,k))
case('complex128 writable C',c128.copy());case('complex128 writable F',np.asfortranarray(c128))
ro=c128.copy();ro.flags.writeable=False;case('complex128 read-only',ro)
case('complex64',c128.astype(np.complex64));case('float64',c128.real.copy())
case('zero rank',np.zeros((n,0),complex))
small=np.zeros((12,12),complex);case('with live correction matrix',c128.copy(),live=(small,));case('complex64 with live correction matrix',c128.astype(np.complex64),live=(small,))
x=c128.astype(np.complex64);case('complex64, cap leaves no room for growth',x,budget=x.nbytes+10)
json.dump(out,open('claude_copy_path_test.json','w'),indent=1)
ok=all((o['error'] is None and o['reserved_equals_result_bytes'] and o['rel_error']<1e-5 and o['in_place_allowance_ok'] and o['copy_step_live_or_additional_covers_copy'] and o['second_step_counts_copy_as_live']) for o in out[:-1] if o['name']!='zero rank') and out[-1]['error']=='MemoryError' and out[-1]['reserved_after']==out[-1]['reserved_before']
print('ALL EXPECTATIONS MET' if ok else 'CHECK FAILURES')
