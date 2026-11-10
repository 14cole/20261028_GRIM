from common import *
import hashlib
n=200; f=9.5; a=0.1
sol=BorPecSolver(sphere_pts(a,n), f*1e9)
ka=sol.k*a; m_max=int(np.ceil(ka+4*ka**(1/3)+2))
def build(threads, budget=1.0):
    st=S.StreamingFarBlocks(sol,m_max,efie=True,mfie=True,tile_threads=threads,tile_budget_gb=budget)
    r=(st.Z.copy(),st.K.copy(),st._workers,st._tile_rows,st._tile_sources); st.close(); return r
A=build(4); B=build(4); C=build(1); Dd=build(4,0.05); E=build(2,0.02)
for name,X in (('4thr again',B),('1thr',C),('4thr budget .05',Dd),('2thr budget .02',E)):
    print(name,'workers/rows/sources',X[2:], 'Z bitwise',np.array_equal(A[0],X[0]),'K bitwise',np.array_equal(A[1],X[1]),
          'max rel dZ %.2e dK %.2e'%(np.max(np.abs(A[0]-X[0]))/np.max(np.abs(A[0])), np.max(np.abs(A[1]-X[1]))/np.max(np.abs(A[1]))))
# OMP thread count determinism for native samplers
import ctypes
rng=np.random.default_rng(0); p=20000
rp,zp,rq,zq=rng.uniform(0.01,1,(4,p)); tr=rng.uniform(-1,1,(4,p))
_,_,sin2,cx,sx=K._half_grid_tables(512,np.arange(8),True,'complex')
sg=K._native_pair_sampler('g'); sb=K._native_pair_sampler('mfie'); si=K._native_pair_sampler('ibc')
for k in (40.0, 40-7j):
    g1=sg((rp,zp,rq,zq),complex(k),sin2,1); g4=sg((rp,zp,rq,zq),complex(k),sin2,4)
    b1=sb((rp,zp,tr[0],tr[1],rq,zq,tr[2],tr[3]),complex(k),cx,sx,1); b4=sb((rp,zp,tr[0],tr[1],rq,zq,tr[2],tr[3]),complex(k),cx,sx,4)
    print('k',k,'OMP 1 vs 4 bitwise: g',np.array_equal(g1,g4),'brackets',all(np.array_equal(x,y) for x,y in zip(b1,b4)))
    S._NATIVE.ghost_set_pair_sampler_isa(0); g0=sg((rp,zp,rq,zq),complex(k),sin2,2); b0=sb((rp,zp,tr[0],tr[1],rq,zq,tr[2],tr[3]),complex(k),cx,sx,2); S._NATIVE.ghost_set_pair_sampler_isa(1)
    print('   portable vs avx2 bitwise: g',np.array_equal(g1,g0),'brackets',all(np.array_equal(x,y) for x,y in zip(b1,b0)))
    # vs numpy
    R=np.sqrt(((rp-rq)**2+(zp-zq)**2)[:,None]+4*(rp*rq)[:,None]*sin2); gn=np.exp(-1j*k*R)/(4*np.pi*R)
    print('   native vs numpy g max rel',np.max(np.abs(g1-gn)/np.abs(gn)))
