"""Reviewer star-harness runner, no hooks: production code of the tree under GRIM_ROOT."""
import os,sys,json,runpy
from pathlib import Path
sys.path[:0]=[os.environ['MONOSTATIC_AUDIT'],str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST')]
spec=json.loads(sys.argv[1]);sys.argv=['monostatic.py',json.dumps(spec)]
runpy.run_path(str(Path(os.environ['MONOSTATIC_AUDIT'])/'monostatic.py'),run_name='__main__')
