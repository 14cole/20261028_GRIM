"""Fresh-process bounded suite. Numerical jobs overlap only during correctness.
Performance comparisons run serially after those jobs exit.
"""
import os,sys,time,json,subprocess,concurrent.futures
from pathlib import Path
HERE=Path(__file__).resolve().parent
env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',GRIM_ROOT=env.get('GRIM_ROOT','/workspace/grim-fmm-followup'))
env['LD_LIBRARY_PATH']=env.get('LD_LIBRARY_PATH','/workspace/fmm-libraries/toolchain/usr/lib/x86_64-linux-gnu')

def run(script,name,spec):
    spec=dict(spec,out='results/'+name)
    (HERE/'results'/f'{name}-spec.json').write_text(json.dumps(spec,indent=2)+'\n')
    start=time.time();print('START',name,flush=True)
    with open(HERE/'results'/f'{name}.json','w') as out,open(HERE/'results'/f'{name}.stderr','w') as err:
        p=subprocess.run([sys.executable,str(HERE/script),json.dumps(spec)],cwd=HERE,env=env,stdout=out,stderr=err)
    print('DONE',name,'exit',p.returncode,'seconds',round(time.time()-start),flush=True)
    if p.returncode:raise RuntimeError(name)
    return json.loads((HERE/'results'/f'{name}.json').read_text())

def matrices():
    for name,spec in [
      ('matrix-stadium-1536',dict(n=1536,shape='stadium',k=[40,-.8],permute=19)),
      ('matrix-concentric-1600',dict(n=1600,shape='concentric',k=[40,-.8],permute=9)),
    ]:
        run('combined_benchmark.py',name,dict(spec,mode='moment_hybrid_nodal',tol=1e-13,full=True,require_compression=True))

def solves():
    for name,spec in [
      ('pre-1024-TE-loose',dict(n=1024,k=80,pol='TE',op_tol=.01,inv_tol=.01,dense_reference=True)),
      ('pre-1024-TM-tight',dict(n=1024,k=80,pol='TM',op_tol=.001,inv_tol=.001,dense_reference=True)),
      ('pre-4096-TE-loose',dict(n=4096,k=80,pol='TE',op_tol=.01,inv_tol=.01)),
    ]:
        run('preconditioned_solve.py',name,spec)

if __name__=='__main__':
    for pid in map(int,sys.argv[1:]):
        while Path('/proc',str(pid)).exists():time.sleep(2)
    smoke=json.loads((HERE/'results/pre-512-TE.json').read_text())
    assert all(r['status']==0 for r in smoke['results']),smoke['results']
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        fs=[pool.submit(matrices),pool.submit(solves)]
        for f in fs:f.result()
    for mode in ['stream','moment_stream','moment_hybrid_nodal']:
        run('combined_benchmark.py','perf-2048-'+mode,dict(n=2048,shape='star',mode=mode,tol=1e-13,warmups=2,repeats=7))
    run('combined_benchmark.py','perf-4096-moment_hybrid_nodal',dict(n=4096,shape='star',mode='moment_hybrid_nodal',tol=1e-13,warmups=2,repeats=7,require_compression=True))
    for mode in ['stream','moment_stream']:
        run('combined_benchmark.py','allnear-512-'+mode,dict(n=512,shape='star',k=[6,0],mode=mode,tol=1e-13,warmups=2,repeats=7))
    print('SUITE COMPLETE',flush=True)
