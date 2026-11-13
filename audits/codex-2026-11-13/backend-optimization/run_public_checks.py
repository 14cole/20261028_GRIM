import os,sys,json,subprocess
for body in ['pec','diel']:
 for mode in ['dense','compressed']:
  for variant,root in [('baseline',os.environ.get('GRIM_BASE_ROOT','/workspace/grim-fmm-followup')),('candidate',os.environ.get('GRIM_CANDIDATE_ROOT','/workspace/backend-optimization-study/candidate'))]:
   spec=dict(body=body,mode=mode,out=f'results/public-{body}-{mode}-{variant}')
   with open(spec['out']+'.stderr','w') as err:
    p=subprocess.run([sys.executable,'public_smoke.py',json.dumps(spec)],stderr=err,env={**os.environ,'GRIM_ROOT':root,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
   print(spec['out'],p.returncode,flush=True)
   if p.returncode:raise SystemExit(p.returncode)
