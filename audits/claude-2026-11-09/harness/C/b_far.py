from common import *
import resource, tracemalloc
n=int(sys.argv[1]); f=float(sys.argv[2]); threads=int(sys.argv[3]); fam=sys.argv[4] if len(sys.argv)>4 else 'cfie'
a=0.1
sol=BorPecSolver(sphere_pts(a,n), f*1e9)
ka=sol.k*a; m_max=int(np.ceil(ka+4*ka**(1/3)+2))
print('n',n,'ka',round(ka,1),'m_max',m_max,'P',sol.P, 'gap', sol._far_gap())
T=CpuTimers()
T.wrap(K,'_project_half_grid'); T.wrap(K,'_half_grid_tables'); T.wrap(K,'_far_sample_counts')
orig=K._native_pair_sampler
def nps(kind):
    s=orig(kind)
    def w(*a):
        t=time.thread_time(); r=s(*a); dt=time.thread_time()-t
        with T.lock: T.t['native_sample_'+kind]=T.t.get('native_sample_'+kind,0)+dt; T.c['native_sample_'+kind]=T.c.get('native_sample_'+kind,0)+1
        return r
    return w
K._native_pair_sampler=nps
T.wrap(K,'banded_modal_kernels'); T.wrap(S,'_efie_band'); T.wrap(S,'_bracket_band'); T.wrap(S,'_banded_stream')
T.wrap(S,'_add_band_to_packed'); T.wrap(S,'_add_band_to_store')
t=time.time(); c=time.process_time()
st=S.StreamingFarBlocks(sol,m_max,efie=True,mfie=(fam=='cfie'),tile_threads=threads)
print('wall',round(time.time()-t,2),'cpu',round(time.process_time()-c,2),'workers',st._workers,'native_threads',st._native_threads,'tile rows',st._tile_rows,'tile sources',st._tile_sources,'work',st._work_bytes/1e6,'nx',st._nx_e,st._nx_b)
print('store GB',st.memory_gb(),'maxrss MB',resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
T.report()
