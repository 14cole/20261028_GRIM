"""Run the unchanged prior physical harness with a selected research solver."""
import importlib,json,os,runpy,sys
from collections import Counter
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
AUDIT=Path(os.environ['MONOSTATIC_AUDIT'])
sys.path[:0]=[str(HERE/'claude'),str(AUDIT),str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST')]
spec=json.loads(sys.argv[1]);variant=spec.pop('variant')
module=importlib.import_module({'v3':'block_gmres_right','z':'block_gmres_right_z','diagnostic':'diagnostic_solver'}[variant])
import block_gmres
restart=spec.pop('restart_blocks',20)
def selected(*args,**kwargs):
    return module.solve(*args,restart_blocks=restart,**kwargs)
block_gmres.solve=selected
if variant=='diagnostic':
    from ghost_backend.compressed.hmatrix_factor import HMatrixSystem
    original=HMatrixSystem.__init__
    def initialized(self,*args,**kwargs):
        original(self,*args,**kwargs)
        seen=set();arrays=[]
        def walk(value,path):
            if id(value) in seen:return
            seen.add(id(value))
            if isinstance(value,np.ndarray):arrays.append(dict(path=path,dtype=str(value.dtype),shape=list(value.shape),bytes=value.nbytes))
            elif isinstance(value,(tuple,list)):
                for i,x in enumerate(value):walk(x,path+'/'+str(i))
            elif hasattr(value,'__dict__'):
                for k,x in vars(value).items():walk(x,path+'/'+k)
        walk(self.root,'root')
        Path(spec['out']+'.inverse-arrays.json').write_text(json.dumps(arrays,indent=2))
    HMatrixSystem.__init__=initialized
sys.argv=['monostatic.py',json.dumps(spec)]
runpy.run_path(str(AUDIT/'monostatic.py'),run_name='__main__')
