import sys, time, cProfile, pstats, resource, os
sys.path.insert(0,'..')
from lib import *
from ghost_backend.bor import dispatch as D
if __name__=='__main__':
    n=int(sys.argv[1]); f=float(sys.argv[2]); out=sys.argv[3]
    g=bor_sphere(0.1,n)
    pr=cProfile.Profile(); t=time.time(); pr.enable()
    r=D.solve_monostatic_rcs_bor(g,[f],[0.0,30.0,60.0,90.0],geometry_units='meters')
    pr.disable(); dt=time.time()-t
    print('wall',dt,'maxrss MB',resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024, 'children MB', resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss/1024)
    md=r['metadata']
    for kk in ('modes_used','near_quadrature','timings','bor_execution_options','per_frequency'):
        if kk in md: print(kk, str(md[kk])[:1500])
    print([ (s['polarization'],s['theta_inc_deg'],round(s['rcs_db'],4)) for s in r['samples']])
    pr.dump_stats(out)
    st=pstats.Stats(out); st.sort_stats('cumulative').print_stats(60)
    st.sort_stats('tottime').print_stats(35)
