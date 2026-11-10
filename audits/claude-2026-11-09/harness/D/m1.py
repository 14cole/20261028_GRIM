from dlib import *
a=0.1
asp=[0,37,90,143,180]
def report(tag, g, ka, exact, **kw):
    f=f_for_ka(ka,a)
    t=time.time()
    try:
        r=run(g,f,asp,**kw)
    except Exception as e:
        print(f'{tag:28s} ka={ka:7.4f} FAIL {type(e).__name__}: {str(e)[:200]}'); return
    vv,_=chan(r,'VV'); hh,_=chan(r,'HH')
    ex=exact(f*1e9)
    allv=np.concatenate([vv,hh])
    err=db(allv)-db(ex)
    pf=r['metadata']['per_frequency'][0]
    print(f'{tag:28s} ka={ka:7.4f} n={pf["n_unknowns"]:5d} modes={pf["modes_used"]:3d} exact={db(ex):9.4f}dB errmax={np.max(np.abs(err)):8.4f} dB (mean {np.mean(err):+.4f}) spread={np.ptp(db(allv)):.4f} dB vvhh0={abs(db(vv[0])-db(hh[0])):.1e} cond={pf["max_cond"]:.2e} t={time.time()-t:.1f}s {r["metadata"]["formulation"]}', flush=True)
import sys
which=sys.argv[1]
n=60
if which=='pec':
    for ka in [0.5,1.0,2.0,2.7437,3.0,4.4934,5.0,5.7635,7.7253,10.0]:
        report('pec', sphere(a,n), ka, lambda fh: SP.sigma_pec_sphere(a,fh))
if which=='ibc':
    for zs in [50+0j, 200+100j, 100-150j, 377+0j, 0.001+100j,0-200j, 20+0j]:
        for ka in [1.0,2.7437,4.4934,6.0]:
            report(f'ibc {zs}', sphere(a,n,'ibc',zs=zs), ka, lambda fh: SP.sigma_impedance_sphere(a,fh,zs))
if which=='sheet':
    for zs in [50+0j, 200+100j, 100-150j, 1000+0j,0+100j]:
        for ka in [1.0,2.7437,4.4934]:
            report(f'sheet {zs}', sphere(a,n,'sheet',zs=zs), ka, lambda fh: SP.sigma_electric_sheet_sphere(a,fh,zs))
if which=='diel':
    for eps,mu in [(2.5,1),(4-0.2j,1),(2.5-0.04j,1.3-0.02j),(10,1),(4-4j,1),(1.0001,1),(1,3-0.5j),(36-1j,1)]:
        for ka in [0.5,1.5,3.0]:
            report(f'diel {eps} {mu}', sphere(a,n,'diel',eps=eps,mu=mu), ka, lambda fh: SP.sigma_dielectric_sphere(a,eps,mu,fh))
if which=='coat':
    for eps,mu,b in [(2.5,1,0.08),(4-0.2j,1,0.09),(2.5-0.04j,1.3-0.02j,0.08),(4-0.5j,2-1j,0.095),(3,1,0.05)]:
        for ka in [1.0,3.0,5.0]:
            report(f'coat {eps} {mu} b={b}', coated(b,a,n,eps,mu), ka, lambda fh: SP.sigma_coated_pec_sphere(b,a,eps,mu,fh))
if which=='ml':
    for (r,e,m) in [([0.06,0.08,0.1],[4-0.2j,2.0],[1,1]), ([0.07,0.085,0.1],[3-0.1j,5-1j],[1.5-0.2j,1]), ([0.05,0.07,0.085,0.1],[2,4-0.3j,2.5],[1,1,1])]:
        segs=[]; diel=''
        L=len(e)
        # layer j (inner->outer) flag j+1
        for j in range(L):
            ee=complex(e[j]); mm=complex(m[j]); diel+=f'{j+1} {ee.real} {ee.imag} {mm.real} {mm.imag}\n'
        segs.append(('o',3,f'3 1 0 {L} 0',arc_rows(r[-1],n)))
        for j in range(L-1,0,-1):
            segs.append((f'i{j}',5,f'5 1 0 {j+1} {j}',arc_rows(r[j],n)))
        segs.append(('c',4,'4 1 0 1 0',arc_rows(r[0],n)))
        g=geo(segs,diel=diel)
        for ka in [1.0,3.0]:
            report(f'ml{L}', g, ka, lambda fh: SP.sigma_multilayer_pec_sphere(r,e,m,fh))
