"""Isolate the actual gather change's temporary allocations, not whole-solve RSS."""
import os,sys,ast,json,tracemalloc,gc
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST'))
from ghost_backend.compressed.hmatrix import BlockRow
base=Path(os.environ['BASE_GRIM_ROOT'])/'tools/GHOST/ghost_backend/compressed/hmatrix.py'
cls=next(x for x in ast.parse(base.read_text()).body if isinstance(x,ast.ClassDef) and x.name=='BlockRow')
method=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='values')
ns={'np':np};exec(compile(ast.Module(body=[method],type_ignores=[]),str(base),'exec'),ns)
results=[]
for height,width,side in [(256,8192,149),(512,16384,256),(1024,32768,1024)]:
    u=np.ones((height,width),complex);br=BlockRow(0,0,height,[(0,width)],u,None);ids=np.arange(side);measure={};hashes=[]
    for label,fn in [('baseline',ns['values']),('candidate',BlockRow.values)]:
        gc.collect();tracemalloc.start();tracemalloc.reset_peak();a=fn(br,ids,ids);_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        assert a.shape==(side,side) and np.all(a==1);measure[label]=peak;del a
    assert measure['candidate']<measure['baseline']
    results.append(dict(height=height,width=width,query_side=side,result_bytes=side*side*16,peak_temporary_bytes=measure))
    del u,br
Path(__file__).with_name('gather-allocation.json').write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
