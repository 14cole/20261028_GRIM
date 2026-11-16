"""Reviewer star-harness runner with the audit/builder hooks."""
import os,sys,json,runpy
from pathlib import Path
sys.path[:0]=[os.environ['MONOSTATIC_AUDIT'],str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST')]
import claude_audit
spec=json.loads(sys.argv[1]);claude_audit.install(spec)
sys.argv=['monostatic.py',json.dumps(spec)]
try:runpy.run_path(str(Path(os.environ['MONOSTATIC_AUDIT'])/'monostatic.py'),run_name='__main__')
finally:Path(spec['out']+'.hooks.json').write_text(json.dumps(dict(claude_audit.RECORD,final_memory=claude_audit.memory()),indent=2,default=str))
