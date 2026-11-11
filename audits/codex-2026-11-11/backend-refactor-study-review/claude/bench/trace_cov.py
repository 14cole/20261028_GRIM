import json, os, subprocess, sys
root=sys.argv[1]
runs={'dense':dict(backend='dense'),'tile':dict(backend='compressed'),'hmatrix':dict(backend='compressed',env={'GHOST_HMATRIX_MIN_UNKNOWNS':1024})}
bodies=[dict(body='pec',n=1500),dict(body='diel',n=800),dict(body='coated',n=1530),dict(body='airfoil',f=1.0), dict(body='pec',n=1200,entry='solve_monostatic_rcs_2d_certified',options=dict(mesh_strategy='adaptive'))]
for name,extra in runs.items():
    for i,b in enumerate(bodies):
        spec=dict(b,angles=31,**extra)
        env=dict(os.environ,COVERAGE_FILE='covdata/%s'%name)
        r=subprocess.run([sys.executable,'-m','coverage','run','--source',root+'/tools/GHOST/ghost_backend','--parallel-mode','case.py',root,json.dumps(spec)],env=env,capture_output=True,text=True)
        print(name,i,r.returncode,r.stdout[-200:].replace('\n',' '),r.stderr[-200:],flush=True)
