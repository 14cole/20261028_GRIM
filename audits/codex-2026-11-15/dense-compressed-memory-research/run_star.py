import os,sys,json,runpy,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[os.environ['MONOSTATIC_AUDIT'],str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST')]
from hooks import install,RECORD,memory
spec=json.loads(sys.argv[1]);install(spec)
sys.argv=['monostatic.py',json.dumps(spec)]
try:runpy.run_path(str(Path(os.environ['MONOSTATIC_AUDIT'])/'monostatic.py'),run_name='__main__')
finally:Path(spec['out']+'.hooks.json').write_text(json.dumps(dict(RECORD,final_memory=memory()),indent=2))
