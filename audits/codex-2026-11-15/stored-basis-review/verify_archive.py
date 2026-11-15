"""Internal roundtrip check; requires the original batch NPZ files."""
import hashlib,json,os,platform,sys,subprocess
from pathlib import Path
import numpy as np,scipy
from unpack_arrays import restore
HERE=Path(__file__).resolve().parent
cases=restore(HERE/'publication',HERE/'restored');count=0
manifest=json.loads((HERE/'publication/ARRAYS_MANIFEST.json').read_text())
for label in manifest['cases']:
    with np.load(HERE/'results'/(label+'-batch0000.npz')) as a,np.load(HERE/'restored/results'/(label+'.npz')) as b:
        assert set(a.files)==set(b.files)
        for key in a.files:
            assert a[key].shape==b[key].shape and a[key].dtype==b[key].dtype
            assert a[key].tobytes(order='C')==b[key].tobytes(order='C'),(label,key)
            count+=1
env=dict(os.environ,RESTART_RESULTS=str(HERE/'restored/results'),RESTART_ANALYSIS=str(HERE/'restored/analysis.json'))
with (HERE/'archive-analysis.stdout').open('w') as out:
    subprocess.run([sys.executable,str(HERE/'analyze_results.py')],env=env,stdout=out,check=True)
assert json.loads((HERE/'analysis.json').read_text())==json.loads((HERE/'restored/analysis.json').read_text())
baseline=json.loads((HERE/'production-baseline.json').read_text())
production=Path(os.environ['GRIM_ROOT'])/'tools/GHOST'
for name,expected in baseline['hashes'].items():assert hashlib.sha256((production/name).read_bytes()).hexdigest()==expected,name
result=dict(cases=cases,arrays_bitwise_verified=count,restored_analysis_identical=True,production_files_unchanged=baseline['files'],archive_sha256=manifest['archive_sha256'])
(HERE/'archive-verification.json').write_text(json.dumps(result,indent=2)+'\n')
environment=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,platform=platform.platform(),assembly_threads=1,blas_threads=1,memory_limit=Path('/sys/fs/cgroup/memory.max').read_text().strip(),cpu_quota=Path('/sys/fs/cgroup/cpu.max').read_text().strip())
(HERE/'environment.json').write_text(json.dumps(environment,indent=2)+'\n')
print(json.dumps(result,indent=2))
