import pathlib,subprocess,os,json,time
D=pathlib.Path(__file__).parent
def run(name,spec):
 out=D/name
 if out.with_suffix('.json').exists():return
 spec=dict(spec,out=str(out))
 with out.with_suffix('.json').open('w') as f:
  try:r=subprocess.run(['python',str(D/'point_case.py'),json.dumps(spec)],stdout=f,stderr=subprocess.PIPE,text=True,timeout=180,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
  except subprocess.TimeoutExpired:out.with_suffix('.json').write_text(json.dumps(dict(spec,error='timeout')));return
 if r.stderr:out.with_suffix('.stderr').write_text(r.stderr)
 print(name,r.returncode,flush=True)
if __name__=='__main__':
 run('point-claude',dict(engine='claude',n=4000,k=[60.,0.]))
 for digits in [8,10,12,14]:
  for sep in [1,2,3]:run(f'point-d{digits}-s{sep}',dict(n=4000,k=[60.,0.],digits=digits,separation=sep))
 for k in [[60.,1.],[.5,0.]]:
  run(f'point-complex-{k[0]}',dict(n=2000 if k[0]>1 else 200,k=k,digits=12,separation=3))
