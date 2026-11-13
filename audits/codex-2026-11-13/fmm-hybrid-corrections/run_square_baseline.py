"""Reproduce the pre-correction bug without overwriting corrected source."""
import importlib.util,runpy,sys
from pathlib import Path
base=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('hybrid_galerkin',base/'hybrid_galerkin_original.py')
module=importlib.util.module_from_spec(spec);sys.modules['hybrid_galerkin']=module;spec.loader.exec_module(module)
runpy.run_path(str(base/'square_diag.py'),run_name='__main__')
