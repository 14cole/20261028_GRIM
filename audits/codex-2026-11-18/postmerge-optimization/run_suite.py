import os,sys,json,subprocess,pathlib,time
root=pathlib.Path(__file__).resolve().parent
suite=json.loads((root/sys.argv[1]).read_text())
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
for name,spec in suite:
 out=pathlib.Path(os.environ.get('RESULTS_DIR',root/'results'))/name;out.parent.mkdir(parents=True,exist_ok=True)
 assert not out.with_suffix('.json').exists(),name
 spec=dict(spec,out=str(out))
 override=os.environ.get({'base':'BASE_GRIM_ROOT','prototype':'PROTOTYPE_GRIM_ROOT','new':'NEW_GRIM_ROOT'}[spec.get('variant','base')])
 if override:spec['root']=override
 print('START',name,flush=True);t=time.perf_counter()
 child_env=dict(env,OPENBLAS_NUM_THREADS=str(spec.get('blas_threads',1)))
 with out.with_suffix('.log').open('w') as log:p=subprocess.run([sys.executable,str(root/'run_case.py'),json.dumps(spec)],env=child_env,stdout=log,stderr=subprocess.STDOUT)
 print('END',name,p.returncode,round(time.perf_counter()-t,2),flush=True)
 if p.returncode:raise RuntimeError(name)
