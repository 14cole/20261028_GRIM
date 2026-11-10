from ref import *
import ghost_backend.twod.operators as ops
import warnings, sys, functools; warnings.simplefilter('ignore')
print=functools.partial(print,flush=True)
h=0.01
for k in (5-150j, 100-100j, 1-30j, 150-2j):
    out=[]
    for name,o,s in (('touch90',elem((-h,0),(0,0),0,(0,1)),elem((0,0),(0,h),1,(1,2))),
                     ('touch20 r2',elem((-h,0),(0,0),0,(0,1)),elem((0,0),(-2*h*math.cos(math.radians(20)),2*h*math.sin(math.radians(20))),1,(1,2))),
                     ('gap .3h',elem((0,0),(h,0),0,(0,1)),elem((0.1*h,0.3*h),(1.2*h,0.4*h),1,(2,3))),
                     ('thin .02h',elem((0,0),(h,0),0,(0,1)),elem((0.1*h,0.02*h),(1.2*h,0.02*h),1,(2,3))),
                     ('fixed ratio 1.5',elem((0,0),(h,0),0,(0,1)),elem((0.2*h,1.5*h),(1.2*h,1.6*h),1,(2,3)))):
        R=ref_pair(o,s,k,maxdepth=80)
        S,Kp=ops._sk_blocks_near_linear(o,s,k,True)
        out.append(f"{name} S {relerr(S,R[0]):.1e} K' {relerr(Kp,R[1]):.1e}")
    print(f"k={k} |k|h={abs(k)*h:.2f}: "+"; ".join(out))
