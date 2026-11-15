import os,sys,runpy
from pathlib import Path
sys.path.insert(0,str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST'))
from dense_layout import install
install()
runpy.run_path(str(Path(__file__).with_name('run_geometry_capture.py')),run_name='__main__')
