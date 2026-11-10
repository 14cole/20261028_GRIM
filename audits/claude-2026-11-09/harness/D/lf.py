from dlib import *
import sys
a=0.1; n=40; asp=[0,37,90,143,180]
which=sys.argv[1]
def rep(tag,g,ka,exf,**kw):
    f=f_for_ka(ka,a)
    try: r=run(g,f,asp,**kw)
    except Exception as e: print(f'{tag} ka={ka} FAIL {type(e).__name__}: {str(e)[:220]}',flush=True); return
    vv,_=chan(r,'VV'); hh,_=chan(r,'HH'); allv=np.concatenate([vv,hh]); ex=exf(f*1e9); pf=r['metadata']['per_frequency'][0]
    print(f'{tag:26s} ka={ka:<7} n={pf["n_unknowns"]} modes={pf["modes_used"]} exact={db(ex):9.3f} errmax={np.max(np.abs(db(allv)-db(ex))):8.4f} dB spread={np.ptp(db(allv)):.4f} cond={pf["max_cond"]:.2e} warn={[w[:70] for w in r["metadata"]["warnings"]]} ext={r.get("automatic_mode_cap_extensions")}',flush=True)
if which=='lf':
    for ka in (0.1,0.01,0.001,0.0001):
        rep('pec',sphere(a,n),ka,lambda fh: SP.sigma_pec_sphere(a,fh))
        rep('ibc 100+50j',sphere(a,n,'ibc',zs=100+50j),ka,lambda fh: SP.sigma_impedance_sphere(a,fh,100+50j))
        rep('sheet 100',sphere(a,n,'sheet',zs=100+0j),ka,lambda fh: SP.sigma_electric_sheet_sphere(a,fh,100+0j))
        rep('diel 4-0.2j',sphere(a,n,'diel',eps=4-0.2j),ka,lambda fh: SP.sigma_dielectric_sphere(a,4-0.2j,1,fh))
        rep('coat 4-0.2j b=.08',coated(0.08,a,n,4-0.2j),ka,lambda fh: SP.sigma_coated_pec_sphere(0.08,a,4-0.2j,1,fh))
if which=='big':
    for ka,nn in ((20.0,200),(30.0,300)):
        t=time.time(); rep(f'pec n={nn}',sphere(a,nn),ka,lambda fh: SP.sigma_pec_sphere(a,fh)); print('   t',round(time.time()-t,1))
    t=time.time(); rep('diel 2.5 n=160',sphere(a,160,'diel',eps=2.5),10.0,lambda fh: SP.sigma_dielectric_sphere(a,2.5,1,fh)); print('   t',round(time.time()-t,1))
if which=='ext':
    P=[(0,0.3),(0.1,0.1),(0.1,-0.1),(0,-0.1)]
    g=geo([('b',2,'2 0 0 0 0',rows(P))]); asp2=[0,10,30,60,90,120,150,170,180]
    r0=run(g,3.0,asp2,n_modes=60,mode_tol=1e-13); s0=np.concatenate([chan(r0,'VV')[1],chan(r0,'HH')[1]]); print('explicit 60 tol 1e-13 modes',r0['metadata']['per_frequency'][0]['modes_used'])
    for tol in (1e-13,1e-15,1e-17):
        try:
            r=run(g,3.0,asp2,mode_tol=tol); s=np.concatenate([chan(r,'VV')[1],chan(r,'HH')[1]]); pf=r['metadata']['per_frequency'][0]
            print(f'auto tol={tol}: modes {pf["modes_used"]} cap {pf["mode_cap"]} rel diff vs explicit {np.max(np.abs(s-s0))/np.max(np.abs(s0)):.2e}',flush=True)
        except Exception as e: print(f'auto tol={tol} FAIL {type(e).__name__}: {str(e)[:300]}',flush=True)
