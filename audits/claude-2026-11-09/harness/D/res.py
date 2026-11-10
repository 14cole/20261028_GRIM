from dlib import *
a=0.1; n=60
asp=[0,37,90,143,180]
print('closed TYPE-1 sheet sphere (EFIE) near interior cavity resonances; reference = sheet Mie (Zs=0 -> PEC)')
for zs in (0j, 0.1+0j, 2+0j):
    for ka in (2.70, 2.735, 2.740, 2.742, 2.7437, 2.745, 2.748, 2.755, 4.485, 4.490, 4.4934, 4.497):
        f=f_for_ka(ka,a); ex=SP.sigma_electric_sheet_sphere(a,f*1e9,zs)
        try:
            r=run(sphere(a,n,'sheet',zs=zs),f,asp)
        except Exception as e:
            print(f'zs={zs} ka={ka} FAIL {type(e).__name__}: {str(e)[:160]}',flush=True); continue
        vv,_=chan(r,'VV'); hh,_=chan(r,'HH'); allv=np.concatenate([vv,hh]); pf=r['metadata']['per_frequency'][0]
        print(f'zs={zs} ka={ka:.4f} exact={db(ex):8.3f} errmax={np.max(np.abs(db(allv)-db(ex))):7.3f} dB spread={np.ptp(db(allv)):.3f} cond={pf["max_cond"]:.2e} warnings={len(r["metadata"]["warnings"])} gate={r["metadata"]["quality_gate"]["passed"]}',flush=True)
