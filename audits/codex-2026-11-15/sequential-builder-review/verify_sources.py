"""Verify production files against the preserved pre-study SHA256 inventory."""
import os,json,hashlib,platform,sys
from pathlib import Path
import numpy as np,scipy,scipy.linalg
from threadpoolctl import threadpool_info
HERE=Path(__file__).resolve().parent
root=Path(os.environ['GRIM_ROOT'])/'tools/GHOST'
prior=json.loads((Path(os.environ['MONOSTATIC_AUDIT'])/'environment.json').read_text())
checks={p:hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in prior['production_hashes'].items()}
assert all(checks.values()),[p for p,v in checks.items() if not v]
record=dict(parent='79618d58db7351fac5580c5c6bd5529d0e91eb4e',production_files_verified=len(checks),production_hashes=prior['production_hashes'],production_changed=False,
 python=sys.version,numpy=np.__version__,scipy=scipy.__version__,platform=platform.platform(),blas_libraries=threadpool_info(),affinity_cpu_count=len(os.sched_getaffinity(0)),
 memory_limit=Path('/sys/fs/cgroup/memory.max').read_text().strip(),cpu_quota=Path('/sys/fs/cgroup/cpu.max').read_text().strip(),
 cpu_model=next(x.split(':',1)[1].strip() for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name')),
 thread_policy='1 assembly/BLAS except matched four-thread partial-TM Compressed/Dense cases')
(HERE/'environment.json').write_text(json.dumps(record,indent=2));print('Unchanged production files:',len(checks))
