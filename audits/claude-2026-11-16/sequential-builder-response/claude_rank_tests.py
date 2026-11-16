"""Reviewer unit tests of Codex's rank_guard.convert_factor, written before reading its tests."""
import numpy as np,json
from rank_guard import convert_factor
from codex_hooks import convert
r=np.random.default_rng(11);n=lambda *s:r.standard_normal(s)+1j*r.standard_normal(s);out=[]
def case(name,a,key,expect):
    b,rec=convert_factor(a,key);kind='complex64' if b.dtype==np.complex64 else 'double-retained'
    g,_=convert(a);gk='complex64' if g.dtype==np.complex64 else 'double-retained'
    out.append(dict(name=name,key=key,result=kind,global_guard_result=gk,expected=expect,ok=kind==expect,worst=rec.get('rank_vector_max_relative_error')));print(out[-1])
d=np.array([1.,1e-20,1e-40,1e-50])
E=n(60,4)*d[None,:];V=n(4,60)*d[:,None]
case('e with tiny columns','e1' and E,'e1','double-retained')
case('v with tiny rows',V,'v12','double-retained')
case('e with tiny ROWS (not a rank direction)',n(4,60).T*0+ (n(60,4)*np.r_[np.ones(59),1e-50][:,None]),'e2','complex64')
case('v with tiny COLUMNS (not a rank direction)',n(4,60)*np.r_[np.ones(59),1e-50][None,:],'v21','complex64')
case('ordinary e',n(60,4),'e1','complex64');case('ordinary v',n(4,60),'v12','complex64')
a=n(60,4);a[:,2]=0;case('e with an all-zero column',a,'e1','complex64')
a=n(4,60);a[1]=0;case('v with an all-zero row',a,'v21','complex64')
case('rank zero e',np.zeros((60,0),complex),'e1','complex64');case('rank zero v',np.zeros((0,60),complex),'v12','complex64')
case('e columns 1 and 1e-30 (inside float32 range)',n(60,2)*np.array([1.,1e-30])[None,:],'e1','complex64')
case('e columns 1 and 1e-39 (float32 denormal)',n(60,2)*np.array([1.,1e-39])[None,:],'e1','double-retained')
case('F-order e with tiny column',np.asfortranarray(E),'e2','double-retained')
case('all tiny e',1e-60*n(60,4),'e1','double-retained')
# compensated products under the rank guard
u=n(60,4);v=n(4,60);Eb=u*d[None,:];Vb=v/d[:,None];ref=Eb@Vb
g,_=convert(Eb);k,_=convert_factor(Eb,'e1')
out.append(dict(name='compensated product error',global_guard=float(np.linalg.norm(g.astype(complex)@Vb-ref)/np.linalg.norm(ref)),rank_guard=float(np.linalg.norm(k.astype(complex)@Vb-ref)/np.linalg.norm(ref))));print(out[-1])
json.dump(out,open('claude_rank_tests.json','w'),indent=1);print('all expectations met',all(o.get('ok',True) for o in out))
