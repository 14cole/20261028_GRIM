from dlib import *
import sys
a=0.1
asp=[0,37,90,143,180]
which=sys.argv[1]
def arc_ap(a,n):
    # area/curvature compensating radius so faceting error is higher order: use circumscribed-inscribed mean
    r=a/np.sqrt(np.sinc(np.pi/n/np.pi))  # a*sqrt((pi/n)/sin(pi/n))
    return arc_rows(r,n)
if which=='order':
    for kind,kw,exf in (('pec',{},lambda fh: SP.sigma_pec_sphere(a,fh)),
                        ('ibc',dict(zs=100+50j),lambda fh: SP.sigma_impedance_sphere(a,fh,100+50j)),
                        ('diel',dict(eps=4-0.2j),lambda fh: SP.sigma_dielectric_sphere(a,4-0.2j,1,fh))):
        for ka in (3.0,):
            f=f_for_ka(ka,a); ex=exf(f*1e9); prev=None
            for n in (20,40,80,160):
                r=run(sphere(a,n,kind,**kw),f,asp); vv,_=chan(r,'VV'); hh,_=chan(r,'HH'); allv=np.concatenate([vv,hh])
                e=np.max(np.abs(db(allv)-db(ex))); rel=np.max(np.abs(allv/ex-1))
                print(f'{kind} ka={ka} n={n:4d} errmax={e:.5f} dB rel={rel:.3e} order={"" if prev is None else round(np.log2(prev/rel),2)} spread={np.ptp(db(allv)):.5f}',flush=True); prev=rel
if which=='cyl':
    # long thin cylinder: a=0.05, L=1.0 at 6 GHz (ka=6.3, kL=126)
    R=0.05; L=1.0; f=6.0
    g=geo([('t',2,'2 0 0 0 0',rows([(0,L/2),(R,L/2)])),('w',2,'2 0 0 0 0',rows([(R,L/2),(R,-L/2)])),('b',2,'2 0 0 0 0',rows([(R,-L/2),(0,-L/2)]))])
    asp2=[0.5,2,5,20,45,80,88,89.5,90]
    t=time.time(); r0=run(g,f,asp2); pf=r0['metadata']['per_frequency'][0]
    print('auto: n',pf['n_unknowns'],'modes',pf['modes_used'],'cap',pf['mode_cap'],'tail',pf['mode_tail_start'],'t',time.time()-t, 'mirror?', pf['modal_execution']['systems'][0].get('backend'))
    s0=np.concatenate([chan(r0,'VV')[0],chan(r0,'HH')[0]])
    print(' VV',np.round(db(chan(r0,'VV')[0]),3)); print(' HH',np.round(db(chan(r0,'HH')[0]),3))
    lam=C0/6e9; print(' PO broadside cyl dBsm', db(2*np.pi*R*L*L/lam), ' PO endcap', db(4*np.pi*(np.pi*R*R)**2/lam**2))
    r1=run(g,f,asp2,n_modes=pf['mode_cap']+12,mode_tol=1e-13); pf1=r1['metadata']['per_frequency'][0]
    s1=np.concatenate([chan(r1,'VV')[0],chan(r1,'HH')[0]])
    print('tight: modes',pf1['modes_used'],'max ddB vs auto',np.max(np.abs(db(s0)-db(s1))))
    for ang in ([0.5],[89.5],[45]):
        r2=run(g,f,ang); pf2=r2['metadata']['per_frequency'][0]; i=asp2.index(ang[0])
        s2=np.concatenate([chan(r2,'VV')[0],chan(r2,'HH')[0]])
        print('single aspect',ang,'modes',pf2['modes_used'],'tail',pf2['mode_tail_start'],'ddB vs tight',db(s2)-db(s1[[i,i+len(asp2)]]))
