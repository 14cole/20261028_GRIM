"""Reviewer unit tests of Codex's bounded convert(), written before reading check_conversion.py."""
import numpy as np,json
from codex_hooks import convert
eps32=float(np.finfo(np.float32).eps);r=np.random.default_rng(3);out=[]
def case(name,a,expect):
    try:
        b,rec=convert(a);kind='complex64' if b.dtype==np.complex64 else 'double-retained'
        same=b is a
        relerr=float(np.max(np.abs(a-b))/max(np.max(np.abs(a)),1e-300)) if a.size else 0.
        res=dict(name=name,result=kind,returned_same_object=bool(same),rel_err_vs_global_max=relerr,finite=bool(np.isfinite(b).all()),lost=rec['lost_components'],ratio=rec['relative_max_component_error'])
    except FloatingPointError as e:res=dict(name=name,result='raised',message=str(e))
    res['expected']=expect;res['ok']=res['result']==expect;out.append(res);print(res)
    return res
n=lambda *s:r.standard_normal(s)+1j*r.standard_normal(s)
case('ordinary',n(50,7),'complex64')
case('all zero',np.zeros((5,4),complex),'complex64')
case('empty',np.zeros((0,4),complex),'complex64')
case('all tiny 1e-60',1e-60*n(20,3),'double-retained')
a=n(40,6);a[3,2]=1e-50+1e-52j;case('tiny entry among normal',a,'complex64')
a=n(40,6);a[0,0]=1e300;case('overflow entry',a,'double-retained')
a=n(10,3);a[1,1]=1+1e-60j;case('one lost component',a,'complex64')
a=n(10,3);a[2,2]=np.nan;case('NaN source',a,'raised')
a=n(10,3);a[2,2]=np.inf;case('Inf source',a,'raised')
case('denormal doubles only',5e-324*np.ones((4,4),complex),'double-retained')
case('scale 1e-30 uniform (inside float32 range)',1e-30*n(30,5),'complex64')
case('scale 1e-44 uniform (float32 denormal range)',1e-44*n(30,5),'double-retained')
case('scale 1e30 uniform',1e30*n(30,5),'complex64')
a=np.asfortranarray(n(300,9));case('F-order',a,'complex64')
a=n(600,9)[::2];case('non-contiguous view',a,'complex64')
a=n(70000,2);case('larger than one chunk',a,'complex64')
# predicted weakness: columns spanning more than float32 range
a=n(50,4)*np.array([1.,1e-20,1e-40,1e-50])[None,:];res=case('columns scaled 1,1e-20,1e-40,1e-50',a,'complex64')
b,_=convert(a);res['column_relative_error']=[float(np.linalg.norm(a[:,j]-b[:,j])/np.linalg.norm(a[:,j])) for j in range(4)]
print('column relative errors',res['column_relative_error'])
# compensating factor: (U*D)(D^-1 V) product error when one factor's column scale is below float32
u=n(50,4);v=n(4,50);d=np.array([1.,1e-20,1e-40,1e-50]);U=u*d[None,:];V=v/d[:,None]
Us,_=convert(U);prod=U@V;err=float(np.linalg.norm(Us.astype(complex)@V-prod)/np.linalg.norm(prod));out.append(dict(name='compensated product error after converting badly column-scaled factor',value=err));print('compensated product relative error',err)
json.dump(out,open('claude_guard_tests.json','w'),indent=1);print('all expectations met',all(o.get('ok',True) for o in out))
