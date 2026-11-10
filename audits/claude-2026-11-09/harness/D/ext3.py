from dlib import *
from ghost_backend.bor import solver as S
P=[(0,0.3),(0.1,0.1),(0.1,-0.1),(0,-0.1)]
g=geo([('b',2,'2 0 0 0 0',rows(P))])
chains=D._chains_from_snapshot(g,1.0); kind=D._classify(chains); groups,tol,axis_tol=D._prepare_bor_groups(chains,kind)
lam=C0/3e9
pts,_,_=D._mesh_generatrix(groups[0],lam,50000,axis_tol)
print('nodes',len(pts),'first nodes',pts[:5])
sv=S.BorPecSolver(pts,3e9)
k=sv.k
for ms in (0,20):
    try:
        blocks,order,err=S._converged_disjoint_blocks(sv.gen,0,sv.gen,2,k,31,('efie','mfie'),signed=False,mode_start=ms)
        print('mode_start',ms,'converged order',order,'err',err)
        for kind_ in ('efie','mfie'):
            b=blocks[kind_]; print('  ',kind_,'shape',b.shape,'max|block| per mode (first comp):',np.array2string(np.max(np.abs(b[0]),axis=(1,2)),precision=2,max_line_width=250))
    except Exception as e: print('mode_start',ms,'FAIL',str(e)[:200])
