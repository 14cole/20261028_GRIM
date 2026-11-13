"""Unmodified 98be27b control scripts, with only the missing CPU state supplied."""
import os,sys,json,runpy
from pathlib import Path
root=Path(os.environ['GRIM_ROOT']);kind=sys.argv[1];spec=json.loads(sys.argv[2])
prior=root/'audits/codex-2026-11-13/fmm-hybrid-corrections'
sys.path.insert(0,str(prior));sys.path.insert(0,str(root/'tools/GHOST'))
from ghost_backend.execution.cpu import CPUState,_STATE
state=CPUState(kernel_only=True);state.reuse_operators=False
script=prior/{'dense':'dense_control.py','compressed':'compressed_control.py','fmm':'preconditioned_solve.py'}[kind]
sys.argv=[str(script),json.dumps(spec)]
with _STATE.override(state):runpy.run_path(str(script),run_name='__main__')
Path(spec['out']+'-kernels.json').write_text(json.dumps(state.table_events,indent=2))
assert state.table_events and any(x['used'] for x in state.table_events)
