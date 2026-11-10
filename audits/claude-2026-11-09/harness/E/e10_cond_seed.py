import sys, os, warnings
backend=sys.argv[1]; n=int(sys.argv[2]); eps=sys.argv[3]; freq=float(sys.argv[4])
opts=dict(mesh_strategy='global', assembly_threads=1, blas_threads=1)
if backend=='lu': opts['factorization']='dense'; os.environ['GHOST_HIERARCHICAL_MIN_UNKNOWNS']='0'
elif backend=='tile': opts['factorization']='compressed'; os.environ['GHOST_HMATRIX_MIN_UNKNOWNS']='0'
elif backend=='hmat': opts['factorization']='compressed'; os.environ['GHOST_HMATRIX_MIN_UNKNOWNS']='1'
sys.path.insert(0,'..'); from lib import *
from ghost_backend.twod import solver as S
g=snap(f"Title: t\nSegment: b 3\nproperties: 3 1 0 1 0\n{circle_rows(0.1,n)}\nIBCS_Resistances:\nDielectrics:\n1 {eps} 1 0\n")
out=[]
for seed in (1,2,3,4,5,6):
    np.random.seed(seed); s0=np.random.get_state()[2]
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        r=S.solve_monostatic_rcs_2d(g,[freq],[0.0,45.0],geometry_units='meters',compute_condition_number=True,strict_quality_gate=False,execution_options=opts)
    md=r['metadata']['channel_metadata']
    out.append((md['VV']['condition_est_max'],md['HH']['condition_est_max']))
    adv=np.random.get_state()[2]!=s0 or True
    print(backend,'seed',seed,'cond VV %.8g HH %.8g'%out[-1],'estimator',md['VV']['condition_estimator'],'global RNG pos before/after',s0,np.random.get_state()[2],flush=True)
a=np.array(out); print(backend,'spread max/min VV %.4f HH %.4f'%(a[:,0].max()/a[:,0].min(),a[:,1].max()/a[:,1].min()))
