from dlib import *
import sys
a=0.1; b=0.08
asp=[0,37,90,143,180]
def arc(r, t0, t1, n):
    th=np.linspace(t0,t1,n+1); p=[(r*np.sin(t), r*np.cos(t)) for t in th]
    if t0==0: p[0]=(0.0,r)
    if abs(t1-np.pi)<1e-12: p[-1]=(0.0,-r)
    return p
def partial_geo(eps, th0=np.pi/2, n=60, N=1, flip=False):
    eps=complex(eps)
    nc=int(round(n*th0/np.pi))
    outer=arc(a,0,th0,nc)+[(b*np.sin(th0), b*np.cos(th0))]
    cov=arc(b,0,th0,nc); bare=arc(b,th0,np.pi,n-nc)
    # exact junction coordinates
    cov[-1]=outer[-1]; bare[0]=outer[-1]
    segs=[('o',3,f'3 {N} 0 1 0',rows(outer)),('c',4,f'4 {N} 0 1 0',rows(cov)),('b',2,f'2 {N} 0 0 0',rows(bare))]
    return geo(segs,diel=f'1 {eps.real} {eps.imag} 1 0')
def report(tag,r,ex=None):
    vv,_=chan(r,'VV'); hh,_=chan(r,'HH'); pf=r['metadata']['per_frequency'][0]
    s=f'{tag:30s} n={pf["n_unknowns"]} modes={pf["modes_used"]} cond={pf["max_cond"]:.2e} VV={np.round(db(vv),3)} HH={np.round(db(hh),3)}'
    if ex is not None: s+=f' | exact {db(ex):.3f} errmax={np.max(np.abs(db(np.concatenate([vv,hh]))-db(ex))):.4f}'
    print(s, r['metadata']['formulation'],flush=True)
    for w in r['metadata']['warnings']: print('   WARN',w[:160])
    return np.concatenate([vv,hh])
for ka in (1.5,3.0):
    f=f_for_ka(ka,a); ex=SP.sigma_pec_sphere(b,f*1e9)
    for eps in (1.0001,):
        t=time.time()
        try:
            r=run(partial_geo(eps),f,asp); report(f'partial eps={eps} ka={ka}',r,ex); print('   t',time.time()-t)
        except Exception as e: print('FAIL',type(e).__name__,str(e)[:400])
# real material: refinement self-consistency and VV/HH axial equality
f=f_for_ka(3.0,a)
res={}
for n in (40,80):
    try:
        r=run(partial_geo(3-0.3j,n=n),f,asp); res[n]=report(f'partial eps=3-0.3j n={n}',r)
    except Exception as e: print('FAIL',type(e).__name__,str(e)[:400])
if len(res)==2: print('40 vs 80 max ddB', np.max(np.abs(db(res[40])-db(res[80]))))
