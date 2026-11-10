from ref import *
import ghost_backend.twod.operators as ops
import warnings, sys, functools; warnings.simplefilter('ignore')
print=functools.partial(print,flush=True)
h=0.01
def err(o,s,k):
    R=ref_pair(o,s,k,maxdepth=90)
    S,Kp=ops._sk_blocks_near_linear(o,s,k,True)
    sc=o.length*s.length
    return relerr(S,R[0]), np.max(abs(Kp-R[1]))/max(np.max(abs(R[1])),1e-300)
print("touching rule / fixed 16-pt near rule error vs |k|L (equal panels L=h). columns: S rel err, K' rel err")
for kL in (1.0,1.57,2.0,3.0,4.0,6.0,8.0,12.0,20.0):
  for kk in (kL/h, kL/h*np.exp(-1j*np.pi/6)):
    out=[]
    for name,ang in (('touch90',90),('touch150',150)):
        a=math.radians(ang)
        o=elem((-h,0),(0,0),0,(0,1)); s=elem((0,0),(-h*math.cos(a),h*math.sin(a)),1,(1,2))
        out.append((name,)+err(o,s,kk))
    o=elem((0,0),(h,0),0,(0,1))
    out.append(('near par 1.0h',)+err(o,elem((0.3*h,1.0*h),(1.3*h,1.0*h),1,(2,3)),kk))
    out.append(('near coll gap .3h',)+err(o,elem((1.3*h,0.05*h),(2.3*h,0.3*h),1,(2,3)),kk))
    print(f"kL={kL:5.2f} arg={np.degrees(np.angle(kk)):5.0f}: "+"; ".join(f"{n} {a:.1e}/{b:.1e}" for n,a,b in out))
