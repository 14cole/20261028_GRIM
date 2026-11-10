from common import *
n=int(sys.argv[1]); f=float(sys.argv[2]); a=0.1
sol=BorPecSolver(sphere_pts(a,n), f*1e9)
ka=sol.k*a; m_max=int(np.ceil(ka+4*ka**(1/3)+2))
print('n',n,'m_max',m_max)
for rep in range(2):
    for budget in (1.0,0.25,0.06,0.02):
        c=time.process_time(); t=time.time()
        st=S.StreamingFarBlocks(sol,m_max,efie=True,mfie=True,tile_threads=4,tile_budget_gb=budget)
        print(f'rep {rep} budget {budget}: tile {st._tile_rows}x{st._tile_sources} workers {st._workers}: process cpu {time.process_time()-c:.2f}s wall {time.time()-t:.2f}s',flush=True)
        st.close()
