import os,sys,time,json
from lib import *
from ghost_backend.twod import solver as S
n=int(sys.argv[1]); meth=sys.argv[2]; na=int(sys.argv[3])
g=circle_geo(0.1,n)
t=time.time(); c=time.process_time()
r=S.solve_monostatic_rcs_2d(g,[1.0],list(np.linspace(0,180,na)),geometry_units='meters',solver_method=meth)
m=r['metadata']
def find(d,pat,pre=''):
    out=[]
    if isinstance(d,dict):
        for k,v in d.items():
            if isinstance(v,(dict,list)): out+=find(v,pat,pre+k+'.')
            elif any(p in k for p in pat): out.append((pre+k,v))
    elif isinstance(d,list):
        for i,v in enumerate(d[:2]): out+=find(v,pat,pre+str(i)+'.')
    return out
print(n,meth,na,'wall',round(time.time()-t,2),'cpu',round(time.process_time()-c,2))
if len(sys.argv)>4:
    for k,v in find(m,['factoriz','backend','threads','solver_method','seconds','stage']): print('  ',k,v)
