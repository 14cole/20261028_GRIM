import os,sys,subprocess,json,time
for i,case in enumerate([
 dict(n=1024,k=40,check_adjoint=True),
 dict(n=512,k=40,pol='TM',eps=[4.,0.],star=False,check_adjoint=True,threads=4),
 dict(n=64,k=2,pol='TE',eps=[3.,-.8],fallback=True,check_adjoint=True),
]):
 for mode,root in [('baseline',os.environ.get('GRIM_BASE_ROOT','/workspace/grim-fmm-followup')),('candidate',os.environ.get('GRIM_CANDIDATE_ROOT','/workspace/backend-optimization-study/candidate'))]:
  spec=dict(case,out=f'results/physical-{i}-{mode}')
  with open(spec['out']+'.json','w') as out,open(spec['out']+'.stderr','w') as err:
   p=subprocess.run([sys.executable,'compressed_control.py',json.dumps(spec)],stdout=out,stderr=err,env={**os.environ,'GRIM_ROOT':root,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
  print(spec['out'],p.returncode,flush=True)
  if p.returncode:raise SystemExit(p.returncode)
