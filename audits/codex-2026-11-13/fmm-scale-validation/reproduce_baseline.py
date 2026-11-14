"""Reproduce the first 32k run: bounded full-row validation, original scale rule.
The corrected policy and streamed validation are used by every other run.
"""
import os,sys,runpy,importlib.util
from pathlib import Path
here=Path(__file__).resolve().parent
sys.path.insert(0,os.environ['GRIM_ROOT']+'/tools/GHOST');sys.path.insert(0,str(here/'fmm'))
for name,file in [('safe_cross','baseline_safe_cross.py'),('preconditioned_solve','baseline_driver_32768.py')]:
 spec=importlib.util.spec_from_file_location(name,here/file);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
runpy.run_path(str(here/'native_fmm_control.py'),run_name='__main__')
