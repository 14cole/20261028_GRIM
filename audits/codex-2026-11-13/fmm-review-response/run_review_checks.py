import pathlib,json,subprocess,os,time,resource
D=pathlib.Path(__file__).parent;env=dict(os.environ,GRIM_ROOT=os.environ.get('GRIM_ROOT','/workspace/grim-fmm-followup'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',LD_LIBRARY_PATH='/workspace/fmm-libraries/toolchain/usr/lib/x86_64-linux-gnu')
def run(name,args):
 before=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.perf_counter()
 with (D/(name+'.json')).open('w') as out,(D/(name+'.stderr')).open('w') as err:r=subprocess.run(['python',*args],stdout=out,stderr=err,env=env,timeout=900)
 after=resource.getrusage(resource.RUSAGE_CHILDREN);(D/(name+'-run.json')).write_text(json.dumps(dict(exit_code=r.returncode,wall_seconds=time.perf_counter()-start,user_cpu_seconds=after.ru_utime-before.ru_utime,system_cpu_seconds=after.ru_stime-before.ru_stime)))
 print(name,r.returncode,round(time.perf_counter()-start,2),flush=True)
for engine,rep in [('native',0),('cached',0),('cached',1)]:
 name=f'setup-{engine}-{rep}';run(name,[str(D/'galerkin_case.py'),json.dumps(dict(engine=engine,n=4000,k=[41.91690043903363,0],radius=2.54,operators=['S','W'],repeats=3,out=str(D/name)))])
for name in ['two-circles-gap-1e-4','level-transition-3-4b','square-graded']:
 run(name,[str(D/'matrix_check.py'),env['GRIM_ROOT'],name])
