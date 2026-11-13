"""Run the previous FMM experiment with production kernel execution enabled."""
import os,sys,json,runpy
from pathlib import Path
root=Path(os.environ.get('GRIM_ROOT','/workspace/grim-fmm-followup'))
previous=root/'audits/codex-2026-11-13/fmm-hybrid-corrections'
sys.path.insert(0,str(previous));sys.path.insert(0,str(root/'tools/GHOST'))
from ghost_backend.execution.cpu import CPUState,_STATE
state=CPUState(kernel_only=True);state.reuse_operators=False
with _STATE.override(state):
 runpy.run_path(str(previous/'preconditioned_solve.py'),run_name='__main__')
Path(json.loads(sys.argv[1])['out']+'-kernel-events.json').write_text(json.dumps(state.table_events,indent=2))
