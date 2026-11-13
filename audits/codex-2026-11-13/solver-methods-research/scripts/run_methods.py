import json,os,pathlib,subprocess,time
D=pathlib.Path(__file__).parent
ROOT=os.environ.get('GRIM_ROOT','/workspace/grim-fmm-study')
def run(name,spec,timeout=360):
 path=D/(name+'.json')
 if path.exists() and path.stat().st_size:return
 spec=dict(spec,sample=False,out=str(D/(name+'.npy')))
 started=time.perf_counter()
 with path.open('w') as f:
  try:
   p=subprocess.run(['python',str(D/'sample_solve.py'),ROOT,json.dumps(spec)],stdout=f,stderr=subprocess.PIPE,text=True,timeout=timeout,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
   if p.stderr:(D/(name+'.stderr')).write_text(p.stderr)
  except subprocess.TimeoutExpired:
   path.write_text(json.dumps(dict(spec,error='TimeoutExpired',wall=time.perf_counter()-started)));print(name,'TIMEOUT',flush=True);return
 try:r=json.loads(path.read_text());print(name,r.get('wall'),r.get('error'),flush=True)
 except Exception:print(name,'HARNESS ERROR',flush=True)
if __name__=='__main__':
 for repeat in range(2):
  for body,n in [('diel',4000),('coated',4080)]:
   for target in [3e-15,1e-13]:
    run(f'dense-{body}-{target}-{repeat}',dict(body=body,n=n,mode='dense',angles=181,dense_target=target))
 for body in ['diel','coated']:
  for radius in [.01,100.]:
   for target in [3e-15,1e-13,1e-12]:
    run(f'scale-{body}-{radius}-{target}',dict(body=body,n=2000,radius=radius,mode='dense',angles=19,dense_target=target))
 for target in [3e-15,1e-13]:
  run(f'disk-diel-{target}',dict(body='diel',n=4000,mode='dense',angles=181,dense_target=target,options={'dense_residual_storage':'disk'}))
 for body,n in [('diel',3000),('coated',2000)]:
  for policy,extra in [('control',{}),('scaled',{'scaled_inverse':True}),('coarse',{'coarse_initial':True}),('scaled-coarse',{'scaled_inverse':True,'coarse_initial':True}),('float32',{'inverse_float32':True})]:
   run(f'inverse-{body}-{policy}',dict(body=body,n=n,mode='compressed',angles=19,probe_profile=True,**extra))
