import pathlib,subprocess,os,json,time,sys
D=pathlib.Path(__file__).parent
for n in [512,1024]:
 for kind in ['TE','TM']:
  for engine in ['stream','hybrid_nodal']:
   name=f'system-{n}-{kind}-{engine}';spec=dict(n=n,kind=kind,k=40,star=True,engine=engine,tol=1e-13,incident_angles=[0.,47.],gmres_max_cycles=6,preconditioners=['fmm_near_ilu'],out=str(D/name));t=time.perf_counter()
   with (D/(name+'.json')).open('w') as out,(D/(name+'.stderr')).open('w') as err:
    r=subprocess.run([sys.executable,str(D/'system_case.py'),json.dumps(spec)],env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',LD_LIBRARY_PATH='/workspace/fmm-libraries/toolchain/usr/lib/x86_64-linux-gnu'),stdout=out,stderr=err,timeout=1200)
   (D/(name+'-run.json')).write_text(json.dumps(dict(exit_code=r.returncode,wall_seconds=time.perf_counter()-t)));print(name,r.returncode,time.perf_counter()-t,flush=True)
   if r.returncode:raise SystemExit(r.returncode)
