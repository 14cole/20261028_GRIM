"""Submit locally without SLURM, then execute a real frozen HPC worker and inspect its artifact."""
import sys,os,json,subprocess,math
from pathlib import Path
import numpy as np
root=Path(sys.argv[1]).resolve();here=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'tools/GHOST'))
from ghost_backend.hpc import twod_driver as D
out=here/'hpc-run'
if '--verify-only' not in sys.argv:
    out.mkdir(exist_ok=False);geo=out/'geometry';geo.mkdir();other=out/'empty';other.mkdir()
    D.load_default_settings();settings=D.current_settings()
    n=8000;theta=-np.linspace(0,2*np.pi,n+1);pts=[(np.cos(t),np.sin(t)) for t in theta];pts[-1]=pts[0]
    text='\n'.join('%.15g %.15g %.15g %.15g'%(*pts[i],*pts[i+1]) for i in range(n))
    (geo/'circle.geo').write_text('Title: retry\nSegment: b 2\nproperties: 2 1 0 0 0\n'+text+'\nIBCS_Resistances:\nDielectrics:\n')
    freq=.314/(2*math.pi/n)*299792458/(2*math.pi)/1e9
    changes=dict(OUTPUT_DIR=str(out/'runs'),FRD_DIR=str(geo),OPN_DIR=str(other),FREQUENCIES_GHZ=[freq],AZIMUTHS_DEG=[0.,45.,90.],GEOMETRY_UNITS='meters',MESH_CERTIFICATION=False,FACTORIZATION='compressed',MESH_STRATEGY='global',BASIS_ORDER=1,MESH_GRADING=True,SUBMIT=False,N_NODES=1,N_JOBS=1,CORES_PER_NODE=2,MAX_WORKERS_PER_NODE=1,MEM_PER_NODE='8G',PYTHON_EXE=sys.executable)
    assert all(k in settings for k in changes),[k for k in changes if k not in settings]
    settings.update(changes);script=out/'driver.py'
    script.write_text('\n'.join(k+' = '+repr(v) for k,v in settings.items())+'\nif __name__ == "__main__":\n    from ghost_backend.hpc.twod_driver import run\n    run(globals(), __file__)\n')
    env=dict(os.environ,PYTHONPATH=str(root/'tools/GHOST'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with (out/'submission.log').open('w') as log:
     p=subprocess.run([sys.executable,str(script)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240)
    assert p.returncode==0,'submission failed'
    runs=list((out/'runs').glob('run_*'));assert len(runs)==1;r=runs[0]
    with (out/'worker.log').open('w') as log:
     p=subprocess.run([sys.executable,str(r/'driver_configured.py'),'--worker',str(r),'0','0'],env=dict(env,PYTHONPATH=str(r/'runtime')),stdout=log,stderr=subprocess.STDOUT,timeout=600)
    assert p.returncode==0,'worker failed'
else:
    runs=list((out/'runs').glob('run_*'));assert len(runs)==1;r=runs[0]
files=list((r/'results').rglob('*.grim'));assert len(files)==1,files
with np.load(files[0],allow_pickle=False) as z:
 meta=json.loads(str(z['solver_metadata_json'].item()))['metadata']
 arrays={k:z[k].copy() for k in z.files if z[k].dtype.kind in 'fciub'}
assert meta['linear_backend']=='cpu_hmatrix',meta.keys()
assert meta['compressed_hmatrix_retry'] and meta['quality_gate']['passed']
assert meta['execution_options']['factorization']=='compressed'
with np.load(here/'worker-reference-fields.npz') as reference: b=reference['1'][6:]
a=arrays['rcs_complex'].reshape(-1)
error=float(max(abs(a-b))/max(abs(b)));assert len(a)==6 and error<1e-8,error
(here/'hpc-retry-results.json').write_text(json.dumps(dict(status='passed',metadata=meta,artifact=str(files[0].relative_to(r)),numeric_arrays=len(arrays),norm_scaled_field_error=error),default=str,indent=2)+'\n')
np.savez_compressed(here/'hpc-retry-arrays.npz',**arrays)
print('PASS: frozen HPC worker published checked H-matrix retry',files[0].name,flush=True)
