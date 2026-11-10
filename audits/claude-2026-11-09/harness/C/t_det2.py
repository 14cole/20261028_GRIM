from common import *
n=200; f=9.5; a=0.1
sol=BorPecSolver(sphere_pts(a,n), f*1e9)
ka=sol.k*a; m_max=int(np.ceil(ka+4*ka**(1/3)+2))
def build(threads, budget=1.0):
    st=S.StreamingFarBlocks(sol,m_max,efie=True,mfie=True,tile_threads=threads,tile_budget_gb=budget)
    r=(st.Z.copy(),st.K.copy(),st._workers,st._tile_rows,st._tile_sources); st.close(); return r
A=build(4,0.05)
for i in range(6):
    X=build(4,0.05)
    print(i,X[2:],'Z bitwise',np.array_equal(A[0],X[0]),'K bitwise',np.array_equal(A[1],X[1]),'ndiff Z',int(np.count_nonzero(A[0]!=X[0])),'K',int(np.count_nonzero(A[1]!=X[1])),'max rel %.1e'%(np.max(np.abs(A[1]-X[1]))/np.max(np.abs(A[1]))))
