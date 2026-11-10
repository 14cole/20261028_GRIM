from common import *
import tracemalloc, resource
n=int(sys.argv[1]); f=float(sys.argv[2]); budget=float(sys.argv[3]); threads=int(sys.argv[4]); fam=sys.argv[5]
a=0.1
sol=BorPecSolver(sphere_pts(a,n), f*1e9)
ka=sol.k*a; m_max=int(np.ceil(ka+4*ka**(1/3)+2))
tracemalloc.start()
base=tracemalloc.get_traced_memory()[0]
st=S.StreamingFarBlocks(sol,m_max,efie=True,mfie=(fam=='cfie'),tile_threads=threads,tile_budget_gb=budget, mode_block=4)
cur,peak=tracemalloc.get_traced_memory()
store=st.memory_gb()*1e9
print(f'n {n} m_max {m_max} budget {budget} GB threads {st._workers} tile {st._tile_rows}x{st._tile_sources} work {st._work_bytes/1e6:.0f}MB modes/range {st.mode_block}: store {store/1e9:.3f} GB, transient peak over store {(peak-base-store)/1e9:.3f} GB  -> ratio to budget {(peak-base-store)/1e9/budget:.2f}; far-table cache {K._FAR_TABLE_BYTES[0]/1e6:.0f} MB')
