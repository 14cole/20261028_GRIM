"""usage: e2_case.py CASE BACKEND N [FREQ] ; prints one JSON line"""
import sys, os, json, time, resource
case, backend, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
freq = float(sys.argv[4]) if len(sys.argv)>4 else 10.0
cond = os.environ.get('E_COND','1')=='1'
opts=dict(mesh_strategy='global', assembly_threads=2, blas_threads=2)
if backend=='lu': opts['factorization']='dense'; os.environ['GHOST_HIERARCHICAL_MIN_UNKNOWNS']='0'
elif backend=='hodlr': opts['factorization']='hierarchical'
elif backend=='hodlr_auto': opts['factorization']='dense'; os.environ['GHOST_HIERARCHICAL_MIN_UNKNOWNS']='1'
elif backend=='tile': opts['factorization']='compressed'; os.environ['GHOST_HMATRIX_MIN_UNKNOWNS']='0'
elif backend=='hmat': opts['factorization']='compressed'; os.environ['GHOST_HMATRIX_MIN_UNKNOWNS']='1'
for kv in os.environ.get('E_OPTS','').split(','):
    if '=' in kv:
        k,v=kv.split('='); opts[k]=int(v) if v.lstrip('-').isdigit() else v
sys.path.insert(0,'..'); from lib import *
from ghost_backend.twod import solver as S
import warnings
a=0.1
def geo(segs, ibc='', diel=''):
    s="Title: t\n"
    for name,typ,props,r in segs: s+=f"Segment: {name} {typ}\nproperties: {props}\n{r}\n"
    return snap(s+f"IBCS_Resistances:\n{ibc}\nDielectrics:\n{diel}\n")
if case=='pec': g=geo([('b',2,'2 1 0 0 0',circle_rows(a,n))])
elif case=='ibc': g=geo([('b',2,'2 1 10 0 0',circle_rows(a,n))],ibc='10 constant 120 60 0 0')
elif case=='diel': g=geo([('b',3,'3 1 0 1 0',circle_rows(a,n))],diel='1 4.0 -0.2 1 0')
elif case=='diel_res': g=geo([('b',3,'3 1 0 1 0',circle_rows(a,n))],diel='1 9.0 0 1 0')   # lossless high-eps: near-resonant
elif case=='coat': g=geo([('o',3,'3 1 0 1 0',circle_rows(a,n)),('c',4,'4 1 0 1 0',circle_rows(0.08,n))],diel='1 4.0 -0.2 1 0')
elif case=='coat_thin': g=geo([('o',3,'3 1 0 1 0',circle_rows(a,n)),('c',4,'4 1 0 1 0',circle_rows(a*0.995,n))],diel='1 4.0 -0.5 2 -1')
elif case=='two_pec': g=geo([('b',2,'2 1 0 0 0',circle_rows(a,n//2)),('c',2,'2 1 0 0 0',circle_rows(a,n//2,x0=2*a*1.005))])
elif case=='two_ibc': g=geo([('b',2,'2 1 10 0 0',circle_rows(a,n//2)),('c',2,'2 1 10 0 0',circle_rows(a,n//2,x0=2*a*1.005))],ibc='10 constant 120 60 0 0')
else: raise SystemExit('case?')
ang=list(np.linspace(0,180,int(os.environ.get('E_NANG','7'))))
t=time.time(); err=None
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter('always')
    try:
        r=S.solve_monostatic_rcs_2d(g,[freq],ang,geometry_units='meters',compute_condition_number=cond,strict_quality_gate=False,execution_options=opts)
    except Exception as e:
        import traceback; err=type(e).__name__+': '+str(e)[:300]; tb=traceback.format_exc()[-1500:]
dt=time.time()-t
out=dict(case=case,backend=backend,n=n,freq=freq,t=dt,maxrss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
if err: out.update(error=err, tb=tb)
else:
    out['amp']={p:[[s['rcs_amp_real'],s['rcs_amp_imag']] for s in r['co_solved_samples'][p]] for p in ('VV','HH')}
    md=r['metadata']['channel_metadata']
    for p in ('VV','HH'):
        m=md[p]
        out[p]=dict(cond=m.get('condition_est_max'),estimator=m.get('condition_estimator'),res=m.get('residual_norm_max'),method=m.get('solver_method'),
            backend=m.get('linear_backend'),dofs=m.get('dense_largest_system'),fallback=m.get('dense_fallback_reasons'),
            hier=m.get('hierarchical_factors'),comp=m.get('compressed_factors'),warn=m.get('warnings'),wall=m.get('execution_wall_seconds'),form=m.get('formulation'))
if not err:
    out['profile']=r['metadata'].get('runtime_profile')
    for p in ('VV','HH'):
        out[p]['profile']=r['metadata']['channel_metadata'][p].get('runtime_profile')
    ec=r['metadata'].get('experimental_cpu') or {}
    out['cpu_keys']=list(ec.keys()) if isinstance(ec,dict) else str(type(ec))
    out['memory_estimates']=ec.get('memory_estimates') if isinstance(ec,dict) else None
    out['systems']=ec.get('systems') if isinstance(ec,dict) else None
print('JSON'+json.dumps(out,default=str))
