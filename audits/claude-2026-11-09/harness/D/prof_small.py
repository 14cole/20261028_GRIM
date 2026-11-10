from dlib import *
import cProfile, pstats, json
a=0.1
g=sphere(a,60)
r=run(g,1.0,[0,60,90],workers=1)  # warm imports
pr=cProfile.Profile()
t=time.time(); pr.enable(); r=run(g,[1.0,1.1,1.2,1.3],[0,60,90],workers=1); pr.disable(); print('wall 4 freqs',time.time()-t)
print(json.dumps(r['metadata']['runtime_profile']['stage_seconds']))
st=pstats.Stats(pr); st.sort_stats('cumulative').print_stats(60)
