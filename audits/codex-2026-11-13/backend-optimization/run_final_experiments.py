import os,sys,subprocess,json
base={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'}
subprocess.run([sys.executable,'run_physical_checks.py'],check=True,env=base)
spec=dict(n=4096,k=80,quantize_inverse=True,out='results/quantized-inverse-4096')
with open(spec['out']+'.json','w') as out,open(spec['out']+'.stderr','w') as err:
 p=subprocess.run([sys.executable,'compressed_control.py',json.dumps(spec)],stdout=out,stderr=err,env=base)
 print(spec['out'],p.returncode,flush=True)
# Smaller leaves need validation across electrical size and material before adoption.
for i,case in enumerate([dict(n=2048,k=40,pol='TM',eps=[4.,0.],star=False),dict(n=2048,k=160,pol='TE',eps=[3.,-.8])]):
 for leaf in [256,128]:
  spec=dict(case,leaf=leaf,out=f'results/cluster-{i}-{leaf}')
  with open(spec['out']+'.json','w') as out,open(spec['out']+'.stderr','w') as err:
   p=subprocess.run([sys.executable,'compressed_control.py',json.dumps(spec)],stdout=out,stderr=err,env=base)
  print(spec['out'],p.returncode,flush=True)
subprocess.run([sys.executable,'run_public_checks.py'],check=True,env=base)
with open('results/full-validation.json','w') as out,open('results/full-validation.stderr','w') as err:
 subprocess.run([sys.executable,'validate_large.py'],stdout=out,stderr=err,check=True,env=base)
