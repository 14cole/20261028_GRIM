"""Fresh process comparisons. Defaults include large solves and fallback probes."""
import json, os, subprocess, sys
from pathlib import Path
p=Path(__file__).resolve().parent
root=Path(sys.argv[1]).resolve()
cases=[]
def pair(name, n, cap, **extra):
    options=extra.pop('options',{})
    common=dict(body='diel',n=n,allocation_cpus=4,storage='disk',**extra)
    for prototype in (False,True):
        cases.append(dict(common,case=name+('-candidate' if prototype else '-reference'),
            prototype=prototype,options=dict(options,assembly_tile=128,ram_budget_gib=cap if prototype else 8.)))
pair('d8000',4000,1.6)
pair('d12000',6000,2.8)
pair('serial',2000,1.0,threads=1)
pair('near-rich',1000,1.0,aspect=.01,angles=9)
pair('comb',1000,1.2,shape='comb',frequency_ghz=.05,angles=9)
pair('numpy',128,1.0,fallback=True,angles=9)
pair('numpy-medium',1000,1.0,fallback=True,angles=9)
pair('scipy-kernels',1000,1.0,fallback=True,no_tables=True,angles=9)
cases.append(dict(case='native-small',body='diel',n=128,storage='disk',angles=9,
    options=dict(assembly_tile=128,ram_budget_gib=8.)))
for unequal in (False,True):
    cases.append(dict(case='alloc-unequal' if unequal else 'alloc-fused',body='diel',n=256,
        storage='disk',angles=9,allocation_probe=True,unequal_orders=unequal,
        options=dict(assembly_tile=128,ram_budget_gib=8.)))
pair('lossless',1000,1.0,material='4.0 0.0 1.0 0.0',angles=9)
for degree in (2,3):
    pair('p'+str(degree),96,2.0,angles=9,options=dict(basis_order=degree))
cases.append(dict(case='d8000-refuse-1.3',body='diel',n=4000,storage='auto',prototype=True,
    options=dict(assembly_tile=128,ram_budget_gib=1.3)))
cases.append(dict(case='d8000-default',body='diel',n=4000,storage='disk',options=dict(ram_budget_gib=2.4)))
cases.append(dict(case='d12000-matched-batch',body='diel',n=6000,storage='disk',
    options=dict(ram_budget_gib=8.,assembly_tile=128,angle_batch_size=64)))
env={k:v for k,v in os.environ.items() if not k.startswith('GHOST_')}
env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
for spec in cases:
    if len(sys.argv)>2 and spec['case'] not in sys.argv[2:]:continue
    spec['out']=str(p/'results'/(spec['case']+'.npz'))
    run=subprocess.run([sys.executable,str(p/'study_wrapper.py'),str(root),json.dumps(spec)],
        text=True,capture_output=True,env=env,timeout=600)
    (p/'results'/(spec['case']+'.log')).write_text(run.stderr)
    rows=[line for line in run.stdout.splitlines() if line.startswith('{')]
    if not rows:
        print(spec['case'],'PROCESS FAILED',run.returncode,run.stderr[-3000:],flush=True)
        continue
    answer=json.loads(rows[-1])
    (p/'results'/(spec['case']+'.json')).write_text(json.dumps(answer,indent=2)+'\n')
    print(spec['case'],answer['wall'],answer['peak_gib'],answer['error'],flush=True)
