from dlib import *
import cProfile, pstats, sys, json, resource
P=[(0,0.3),(0.1,0.1),(0.1,-0.1),(0,-0.1)]
f=float(sys.argv[1]) if len(sys.argv)>1 else 12.0
nasp=int(sys.argv[2]) if len(sys.argv)>2 else 19
w=int(sys.argv[3]) if len(sys.argv)>3 else 2
g=geo([('b',2,'2 0 0 0 0',rows(P))])
asp=list(np.linspace(0,180,nasp))
pr=cProfile.Profile()
t=time.time(); pr.enable(); r=run(g,f,asp,workers=w); pr.disable(); dt=time.time()-t
pf=r['metadata']['per_frequency'][0]
print('wall',dt,'n',pf['n_unknowns'],'modes',pf['modes_used'],'cap',pf['mode_cap'],'tail_start',pf['mode_tail_start'],'maxrss MB',resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
rp=r['metadata'].get('runtime_profile'); print(json.dumps(rp,indent=1,default=str)[:6000])
me=pf['modal_execution']; print({k:v for k,v in me.items() if k not in('systems',)})
print('systems[0..2]',me['systems'][:3])
print('near_prep',pf['near_preparation'])
st=pstats.Stats(pr); st.sort_stats('cumulative').print_stats(45)
st.sort_stats('tottime').print_stats(25)
