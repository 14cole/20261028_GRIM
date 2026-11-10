from dlib import *
import json,sys,os
a=0.1; g=sphere(a,60); w=int(sys.argv[1])
r=run(g,1.0,[0,60,90],workers=w)
t=time.time(); r=run(g,[2.0,2.5,3.0],[0,30,60,90,120,150,180],workers=w); dt=time.time()-t
st=r['metadata']['runtime_profile']['stage_seconds']
print(json.dumps(dict(OPENBLAS=os.environ.get('OPENBLAS_NUM_THREADS'),workers=w,wall=round(dt,1),load=os.getloadavg()[0],**{k:round(v,2) for k,v in st.items()})))
