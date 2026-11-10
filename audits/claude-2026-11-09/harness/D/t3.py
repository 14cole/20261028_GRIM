from dlib import *
a=0.1; n=60
asp=[0,37,90,143,180]
def stats(tag,r,ex=None):
    vv,_=chan(r,'VV'); hh,_=chan(r,'HH'); allv=np.concatenate([vv,hh]); pf=r['metadata']['per_frequency'][0]
    s=f'{tag:34s} n={pf["n_unknowns"]} modes={pf["modes_used"]} mean={np.mean(db(allv)):.4f} spread={np.ptp(db(allv)):.4f}'
    if ex is not None: s+=f' errmax={np.max(np.abs(db(allv)-db(ex))):.4f} dB'
    print(s, r['metadata']['formulation'], 'graded', pf.get('graded_impedance_junctions'), flush=True)
    for w in r['metadata']['warnings']: print('   WARN', w[:200])
def half_rows(a,n,lo,hi):
    th=np.linspace(0,np.pi,n+1)[lo:hi+1]; rho=a*np.sin(th); z=a*np.cos(th)
    if lo==0: rho[0]=0
    if hi==n: rho[-1]=0
    return '\n'.join(f'{rho[i]:.15g} {z[i]:.15g} {rho[i+1]:.15g} {z[i+1]:.15g}' for i in range(len(th)-1))
import sys
which=sys.argv[1]
if which=='nonuni':
  for zs in (100+50j, 20+0j, 0+80j):
    for ka in (1.5, 4.4934):
        f=f_for_ka(ka,a); ex=SP.sigma_impedance_sphere(a,f*1e9,zs)
        r=run(sphere(a,n,'ibc',zs=zs),f,asp); stats(f'uniform zs={zs} ka={ka}',r,ex)
        z2=zs*(1+1e-9)
        g=geo([('u',2,'2 1 10 0 0',half_rows(a,n,0,n//2)),('l',2,'2 1 11 0 0',half_rows(a,n,n//2,n))],
              ibc=f'10 constant {zs.real} {zs.imag} 0 0\n11 constant {z2.real!r} {z2.imag!r} 0 0')
        try:
            r=run(g,f,asp); stats(f'2 flags zs,zs(1+1e-9) ka={ka}',r,ex)
        except Exception as e: print('FAIL',type(e).__name__,str(e)[:300])
        # 3 zones cut at different places
        g=geo([('u',2,'2 1 10 0 0',half_rows(a,n,0,17)),('m',2,'2 1 11 0 0',half_rows(a,n,17,41)),('l',2,'2 1 10 0 0',half_rows(a,n,41,n))],
              ibc=f'10 constant {zs.real} {zs.imag} 0 0\n11 constant {z2.real!r} {z2.imag!r} 0 0')
        try:
            r=run(g,f,asp); stats(f'3 zones ka={ka}',r,ex)
        except Exception as e: print('FAIL',type(e).__name__,str(e)[:300])
if which=='pecibc':
    # PEC|IBC sphere: refinement convergence + z-flip invariance
    zs=100+50j; f=f_for_ka(3.0,a)
    res={}
    for nn in (30,60,120):
        g=geo([('u',2,'2 1 0 0 0',half_rows(a,nn,0,nn//2)),('l',2,'2 1 10 0 0',half_rows(a,nn,nn//2,nn))],ibc=f'10 constant {zs.real} {zs.imag} 0 0')
        r=run(g,f,asp); stats(f'PEC|IBC n={nn}',r); res[nn]=np.concatenate([chan(r,'VV')[0],chan(r,'HH')[0]])
        g=geo([('u',2,'2 1 10 0 0',half_rows(a,nn,0,nn//2)),('l',2,'2 1 0 0 0',half_rows(a,nn,nn//2,nn))],ibc=f'10 constant {zs.real} {zs.imag} 0 0')
        r=run(g,f,[180-x for x in asp]); s=np.concatenate([chan(r,'VV')[0],chan(r,'HH')[0]])
        print('   flipped max ddB', np.max(np.abs(db(s)-db(res[nn]))))
    print('30 vs 120', np.max(np.abs(db(res[30])-db(res[120]))), '60 vs 120', np.max(np.abs(db(res[60])-db(res[120]))))
    print('dB values n=120', np.round(db(res[120]),3))
if which=='open':
    f=3.0
    # flat PEC disk radius 0.1 at z=0, type 2 open
    for typ,props,ibc in ((2,'2 0 0 0 0',''),(1,'1 0 10 0 0','10 constant 0 0 0 0'),(1,'1 0 10 0 0','10 constant 200 0 0 0')):
        for pts in ([(0,0),(0.1,0)],[(0.1,0),(0,0)]):
            try:
                g=geo([('d',typ,props,rows(pts))],ibc=ibc)
                r=run(g,f,[0,30,60,90,120,180]); vv,_=chan(r,'VV'); hh,_=chan(r,'HH')
                pf=r['metadata']['per_frequency'][0]
                print('disk typ',typ,ibc,pts,'n',pf['n_unknowns'],'VV',np.round(db(vv),3),'HH',np.round(db(hh),3),r['metadata']['formulation'])
            except Exception as e: print('disk typ',typ,pts,'FAIL',type(e).__name__,str(e)[:300])
    # PO estimate normal incidence disk: sigma=4pi A^2/lam^2
    lam=C0/3e9; A=np.pi*0.01; print('PO broadside disk dBsm', db(4*np.pi*A*A/lam**2))
    # open hemispherical shell
    try:
        g=geo([('h',2,'2 1 0 0 0',half_rows(a,60,0,30))]); r=run(g,f,[0,90,180]); print('hemi shell type2', np.round(db(chan(r,'VV')[0]),3), r['metadata']['formulation'])
    except Exception as e: print('hemi type2 FAIL',type(e).__name__,str(e)[:300])
    try:
        g=geo([('h',1,'1 1 10 0 0',half_rows(a,60,0,30))],ibc='10 constant 0 0 0 0'); r=run(g,f,[0,90,180]); print('hemi shell type1 zs=0', np.round(db(chan(r,'VV')[0]),3),np.round(db(chan(r,'HH')[0]),3), r['metadata']['formulation'])
    except Exception as e: print('hemi type1 FAIL',type(e).__name__,str(e)[:300])
