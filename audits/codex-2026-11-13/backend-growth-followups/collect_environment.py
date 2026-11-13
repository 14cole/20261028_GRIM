import json,sys,platform,os,subprocess,hashlib,io,contextlib
from pathlib import Path
import numpy as np,scipy
out=io.StringIO()
with contextlib.redirect_stdout(out):np.show_config()
root=Path(os.environ['GRIM_ROOT'])
native={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'tools/GHOST').rglob('*') if p.is_file() and p.suffix in ['.dll','.so']}
data=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,platform=platform.platform(),numpy_config=out.getvalue(),native_hashes=native,compiler=subprocess.check_output(['cc','--version'],text=True).splitlines()[0])
for name,path in [('cpu_max','/sys/fs/cgroup/cpu.max'),('memory_max','/sys/fs/cgroup/memory.max')]:
 if Path(path).exists():data[name]=Path(path).read_text().strip()
Path('results/environment.json').write_text(json.dumps(data,indent=2))
