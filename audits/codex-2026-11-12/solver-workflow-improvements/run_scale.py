import subprocess,json,os,pathlib,time
scripts=pathlib.Path(__file__).parent
root=os.environ.get('GRIM_ROOT','/workspace/grim-workflow-improvements'); dest=pathlib.Path(os.environ.get('GRIM_EVIDENCE_DIR',scripts)); dest.mkdir(parents=True,exist_ok=True)
cases=[('diel',2000,r) for r in [100,10,1,.2,.05,.01]]+[('coated',2000,r) for r in [100,1,.01]]+[('pec',2000,r) for r in [100,.01]]
for body,n,r in cases:
 for mode in ['dense','compressed']:
  name=f'scale-{body}-{r:g}-{mode}'; p=dest/(name+'.json')
  if p.exists() and p.stat().st_size:continue
  spec=dict(body=body,n=n,radius=r,mode=mode,angles=19,sample=False,out=str(dest/(name+'.npy')))
  t=time.time()
  with p.open('w') as f: result=subprocess.run(['python',str(scripts/'sample_solve.py'),root,json.dumps(spec)],stdout=f,stderr=subprocess.PIPE,text=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),timeout=240)
  if result.stderr: (dest/(name+'.stderr')).write_text(result.stderr)
  data=json.load(p.open()); print(name,round(time.time()-t,1),data['error'],flush=True)
