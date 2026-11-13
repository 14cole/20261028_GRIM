import os,sys,subprocess,json
for mode,root in [('baseline',os.environ.get('GRIM_BASE_ROOT','/workspace/grim-fmm-followup')),('candidate',os.environ.get('GRIM_CANDIDATE_ROOT','/workspace/backend-optimization-study/candidate'))]:
 for threads in [1,4]:
  spec=dict(threads=threads,out=f'results/hierarchical-{mode}-{threads}')
  with open(spec['out']+'.json','w') as out,open(spec['out']+'.stderr','w') as err:
   subprocess.run([sys.executable,'check_hierarchical.py',json.dumps(spec)],stdout=out,stderr=err,check=True,env={**os.environ,'GRIM_ROOT':root,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
