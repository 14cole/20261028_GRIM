from ref import *
import ghost_backend.twod.operators as ops
import warnings, sys, functools; warnings.simplefilter('ignore')
print=functools.partial(print,flush=True)
def code_pair(o,s,k):
    S,Kp=ops._sk_blocks_near_linear(o,s,k,True)
    _,K=ops._sk_blocks_near_linear(o,s,k,False)
    return S,Kp,K
def show(tag,o,s,k):
    R=ref_pair(o,s,k); R2=ref_pair(o,s,k,order=30,c=0.7)
    C=code_pair(o,s,k)
    sc=o.length*s.length
    print(f"{tag:26s} S rel {relerr(C[0],R[0]):.1e} (ref {relerr(R[0],R2[0]):.1e}) | K' rel {relerr(C[1],R[1]):.1e} abs/LL {np.max(abs(C[1]-R[1]))/sc:.1e} (ref {np.max(abs(R[1]-R2[1]))/sc:.1e}) | K abs/LL {np.max(abs(C[2]-R[2]))/sc:.1e} |K|/LL {np.max(abs(R[2]))/sc:.1e}")
h=0.01
for k in [complex(a) for a in sys.argv[1:]]:
    k=k.real if k.imag==0 else k
    print('--- k',k,' kh=',abs(k)*h)
    e=elem((0,0),(h,0),0)
    Sc=ops._single_layer_block_linear(e,e,k); Sr=ref_self(h,k)
    print(f"{'self':26s} S {relerr(Sc,Sr):.1e}")
    for name,ang,ratio in (('touch collinear',180,1),('touch 90',90,1),('touch 170',170,1),('touch 30',30,1),('touch 10',10,1),('touch 1',1,1),('touch 90 ratio 20',90,20),('touch 5 ratio 0.05',5,0.05),('touch 179.9 ratio 7',179.9,7)):
        a=math.radians(ang)
        o=elem((-h,0),(0,0),0,(0,1))
        s=elem((0,0),(-ratio*h*math.cos(a), ratio*h*math.sin(a)),1,(1,2))
        try: show(name,o,s,k)
        except Exception as ex: print(name,'EXC',repr(ex)[:200])
    for name,(q0,q1) in (('parallel gap 0.3h',((0,0.3*h),(h,0.3*h))),('parallel gap 0.1h',((0,0.1*h),(h,0.1*h))),('parallel gap 0.01h',((0,0.01*h),(h,0.01*h))),
                         ('parallel gap 1e-3h',((0,1e-3*h),(h,1e-3*h))),
                         ('collinear gap 0.3h',((1.3*h,0),(2.3*h,0))),('collinear gap 0.26h',((1.26*h,0),(2.26*h,0))),('collinear gap 0.02h',((1.02*h,0),(2.02*h,0))),
                         ('T hover 0.3h',((0.5*h,0.3*h),(0.5*h,1.3*h))),('T hover 0.51h',((0.5*h,0.51*h),(0.5*h,1.51*h))),('T hover 0.05h',((0.5*h,0.05*h),(0.5*h,1.05*h))),
                         ('skew near',((0.2*h,0.26*h),(1.4*h,0.9*h))),('center 0.76 perp',((0.5*h,0.76*h-0.5*h),(0.5*h,0.76*h+0.5*h))),
                         ('ratio 2.99 offset',((0,2.99*h),(h,2.99*h))),('ratio 1.0',((0,1.0*h),(h,1.0*h))),
                         ('small src near big',((0.4*h,0.27*h),(0.45*h,0.27*h))),('tiny src v.near big',((0.4*h,0.004*h),(0.41*h,0.004*h)))):
        o=elem((0,0),(h,0),0,(0,1)); s=elem(q0,q1,1,(2,3))
        try: show(name,o,s,k)
        except Exception as ex: print(name,'EXC',repr(ex)[:200])
