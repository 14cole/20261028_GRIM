from dlib import *
import sys, pickle, os
P=[(0,0.3),(0.1,0.1),(0.1,-0.1),(0,-0.1)]
f=3.0
asp=list(range(0,181,10))
def body(N): return geo([('b',2,f'2 {N} 0 0 0',rows(P))])
def amps(r): return np.concatenate([chan(r,'VV')[1],chan(r,'HH')[1]])
if not os.path.exists('cert_ref.pkl'):
    r=run(body(-60),f,asp); pickle.dump(amps(r),open('cert_ref.pkl','wb')); print('ref n',r['metadata']['per_frequency'][0]['n_unknowns'],flush=True)
ref=pickle.load(open('cert_ref.pkl','rb'))
for N in [int(x) for x in sys.argv[1:]]:
    t=time.time()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            r=D.solve_monostatic_rcs_bor_certified(body(N),[f],asp,geometry_units='meters',workers=2)
    except Exception as e:
        print('N',N,'FAIL',type(e).__name__,str(e)[:500],flush=True); continue
    md=r['metadata']; mc=md['mesh_convergence']
    a=amps(r); err=20*np.log10(np.abs(a)/np.abs(ref))
    print(f'N={N} t={time.time()-t:.1f}s certified={md.get("mesh_convergence_certified")} mesh={mc["realized_mesh_refinement"][0]["base_elements_total"]}->{mc["realized_mesh_refinement"][0]["fine_elements_total"]}')
    for pol in ('VV','HH'):
        g=mc['polarizations'][pol]
        print(f'   {pol}: gate max_abs_db(floored)={g["max_abs_db"]:.3f} unfloored={g["max_abs_db_unfloored"]:.3f} complex_max={g["complex_max_normalized"]:.4f} est_published_max_db={g.get("estimated_published_max_abs_db")}')
    n=len(asp)
    print('   TRUE error of published result vs N=-60 ref (dB): VV', np.round(err[:n],2))
    print('                                                    HH', np.round(err[n:],2))
    print('   ref dBsm VV', np.round(db(4*np.pi*np.abs(ref[:n])**2),1))
    print('   max |true err| dB', np.max(np.abs(err)), ' rel-to-peak complex err', np.max(np.abs(a-ref))/np.max(np.abs(ref)),flush=True)
