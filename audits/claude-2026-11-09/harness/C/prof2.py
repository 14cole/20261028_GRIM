import sys, time, cProfile, pstats, resource, os
sys.path.insert(0,'..')
from lib import *
from ghost_backend.bor import dispatch as D
from ghost_backend.execution.options import cpu_allocation_scope
from ghost_backend.execution.thread_control import threadpool_limits
if __name__=='__main__':
    n=int(sys.argv[1]); f=float(sys.argv[2]); out=sys.argv[3]; shape=sys.argv[4] if len(sys.argv)>4 else 'sphere'
    if shape=='sphere': g=bor_sphere(0.1,n)
    else:
        from common import cyl_pts
        p=cyl_pts(0.05,0.3,n); rows='\n'.join(f'{p[i,0]:.15g} {p[i,1]:.15g} {p[i+1,0]:.15g} {p[i+1,1]:.15g}' for i in range(len(p)-1))
        g=snap(f"Title: s\nSegment: body 2\nproperties: 2 1 0 0 0\n{rows}\nIBCS_Resistances:\n\nDielectrics:\n\n")
    pr=cProfile.Profile(timer=time.process_time)
    with cpu_allocation_scope(1), threadpool_limits(1):
        t=time.time(); c=time.process_time(); pr.enable()
        r=D.solve_monostatic_rcs_bor(g,[f],[0.0,30.0,60.0,90.0],geometry_units='meters',bor_options={'near_backend':'threads'})
        pr.disable()
    print('wall',time.time()-t,'cpu',time.process_time()-c,'maxrss MB',resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    print([ (s['polarization'],s['theta_inc_deg'],round(s['rcs_db'],4)) for s in r['samples']])
    pr.dump_stats(out)
    st=pstats.Stats(out); st.sort_stats('cumulative').print_stats(70)
    st.sort_stats('tottime').print_stats(40)
