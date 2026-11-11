"""Run the unchanged study profiler under an explicit solver CPU allocation."""
import runpy,sys,json
from pathlib import Path
root,script,spec=sys.argv[1:4]
sys.path.insert(0,str(Path(root)/'tools/GHOST'))
from ghost_backend.execution.options import cpu_allocation_scope
sys.argv=[script,root,spec]
with cpu_allocation_scope(json.loads(spec)['allocation_cpus']):
 runpy.run_path(script,run_name='__main__')
