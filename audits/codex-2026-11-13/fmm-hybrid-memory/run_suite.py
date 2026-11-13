import os,sys,json,pathlib,subprocess,time,resource
D=pathlib.Path(__file__).parent;env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',LD_LIBRARY_PATH='/workspace/fmm-libraries/toolchain/usr/lib/x86_64-linux-gnu');group=sys.argv[1]
if group=='smoke':cases=[dict(n=128,k=[12,0],full=True,leaf=12,mode=m) for m in ['cached','stream','hybrid']]
elif group=='scale':cases=[dict(n=n,k=[40,0],mode=m) for n in [512,1024,2048] for m in ['cached','stream','hybrid']]
elif group=='difficult':cases=[dict(n=512,k=[40,-.8],shape=s,mode=m,full=True) for s in ['gap','coated','graded'] for m in ['stream','hybrid']]
elif group=='large':cases=[dict(n=512,k=[40,0],mode='hybrid_nodal',tol=1e-13,full=True),dict(n=2048,k=[40,0],mode='hybrid_nodal',tol=1e-13)]+[dict(n=4096,k=[40,0],mode=m,tol=1e-13) for m in ['stream','hybrid_nodal','native']]
elif group=='low':cases=[dict(n=n,k=[12,0],mode=m,tol=1e-13) for n in [512,1024] for m in ['stream','hybrid']]
else:raise ValueError(group)
for c in cases:
 name=f"{group}-{c.get('shape','star')}-{c['n']}-{c['mode']}";c['out']=str(D/name);t=time.perf_counter();usage=resource.getrusage(resource.RUSAGE_CHILDREN)
 try:
  with (D/(name+'.json')).open('w') as out,(D/(name+'.stderr')).open('w') as err:r=subprocess.run([sys.executable,str(D/'benchmark.py'),json.dumps(c)],stdout=out,stderr=err,env=env,timeout=1200);code=r.returncode
 except subprocess.TimeoutExpired:code='timeout'
 now=resource.getrusage(resource.RUSAGE_CHILDREN);result=dict(exit_code=code,wall_seconds=time.perf_counter()-t,user_cpu_seconds=now.ru_utime-usage.ru_utime,system_cpu_seconds=now.ru_stime-usage.ru_stime);(D/(name+'-run.json')).write_text(json.dumps(result));print(name,result,flush=True)
 if code!=0:raise SystemExit(code if isinstance(code,int) else 1)
