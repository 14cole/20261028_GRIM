"""Run the unmodified Claude right solver through the original audit harness."""
import os,sys,json,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
AUDIT=Path(os.environ['MONOSTATIC_AUDIT'])
if len(sys.argv)>1:
    sys.path[:0]=[str(HERE/'claude'),str(AUDIT)]
    import block_gmres_right,block_gmres
    block_gmres.solve=block_gmres_right.solve
    import monostatic
    from ghost_backend.execution.options import execution_scope,cpu_allocation_scope
    from ghost_backend.execution.cpu import CPUState,_STATE
    spec=json.loads(sys.argv[1])
    # Use the harness's normal main entry to establish its execution scopes.
    import runpy
    sys.argv=['monostatic.py',json.dumps(spec)]
    runpy.run_path(str(AUDIT/'monostatic.py'),run_name='__main__')
else:
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    (HERE/'reproduced').mkdir(exist_ok=True)
    for geometry,pol in (('square','TE'),('slot','TE'),('slot','TM')):
        name=f'{geometry}-1024-180-{pol}-right';p=HERE/'reproduced'/name
        spec=dict(n=512,k=10,count=180,start=-90,stop=90,method='fmm',krylov='block_gmres',geometry=geometry,pol=pol,batch=256,krylov_batch=8,op_tol=.0001,inv_tol=.0001,out=str(p))
        if p.with_suffix('.time.json').exists():raise RuntimeError('Existing run: '+name)
        started=time.perf_counter()
        with p.with_suffix('.stdout').open('w') as out,p.with_suffix('.stderr').open('w') as err:
            r=subprocess.run([sys.executable,__file__,json.dumps(spec)],env=env,stdout=out,stderr=err)
        p.with_suffix('.time.json').write_text(json.dumps(dict(returncode=r.returncode,wall_seconds=time.perf_counter()-started)))
        print(name,r.returncode,flush=True)
        if r.returncode:raise RuntimeError('Case failed: '+name)
