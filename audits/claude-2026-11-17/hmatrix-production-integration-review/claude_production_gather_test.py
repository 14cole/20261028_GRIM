"""Reviewer test of the ACTUAL production BlockRow.values in the candidate tree against the parent tree's
method, loaded from its source file. Same case matrix as my earlier v2 test (raw bytes, dtype, shape, exception)."""
import os,sys,json,importlib.util
from pathlib import Path
from collections import Counter
import numpy as np
new_root=Path(os.environ['GRIM_ROOT'])/'tools/GHOST';old_root=Path(os.environ['OLD_ROOT'])/'tools/GHOST'
sys.path.insert(0,str(new_root))
from ghost_backend.compressed import hmatrix as new_mod
src=(old_root/'ghost_backend/compressed/hmatrix.py').read_text();start=src.index('    def values(self, rows=None, columns=None):');end=src.index('    def local_columns',start)
ns={'np':np};exec('def values'+src[start:end].split('def values',1)[1].replace('\n    ','\n'),ns);old_values=ns['values']
new_values=new_mod.BlockRow.values;BlockRow=new_mod.BlockRow
assert 'np.ix_' in Path(new_mod.__file__).read_text() and 'np.ix_' not in src[start:end]
r=np.random.default_rng(77);out=dict(cases=0,mismatches=[])
def row(u,v=None):return BlockRow(0,0,u.shape[0],[(0,(u.shape[1] if v is None else v.shape[1]))],u,v)
def run(f,br,rows,cols):
    try:
        y=f(br,rows,cols);return ('ok',y.shape,str(y.dtype),y.tobytes())
    except Exception as e:return ('raise',type(e).__name__)
def check(br,rows,cols,tag):
    out['cases']+=1
    if run(old_values,br,rows,cols)!=run(new_values,br,rows,cols):out['mismatches'].append(tag)
E0=np.array([],np.int64)
for trial in range(300):
    m,w=int(r.integers(1,40)),int(r.integers(1,60));base=r.standard_normal((m,w))+1j*r.standard_normal((m,w));flat=base.reshape(-1)
    specials=[complex(-0.0,0.0),complex(0.0,-0.0),complex(np.inf,-np.inf),complex(np.nan,1.0),complex(float.fromhex('0x1p-1074'),0.0)]
    for i in range(min(flat.size,len(specials))):flat[i]=specials[i]
    if flat.size>5:
        nb=np.array([0x7ff8000000000123],np.uint64).view(np.float64)[0];flat[5]=complex(nb,-nb)
    for layout,u in (('C',np.ascontiguousarray(base)),('F',np.asfortranarray(base)),('strided',np.repeat(np.repeat(base,2,0),2,1)[::2,::2])):
        br=row(u)
        for idt in (np.int64,np.int32,np.uint32):
            check(br,r.integers(0,m,int(r.integers(0,2*m))).astype(idt),r.integers(0,w,int(r.integers(0,2*w))).astype(idt),f'random|{layout}')
        check(br,np.arange(m),np.arange(w),f'full|{layout}');check(br,r.integers(-m,m,4),r.integers(-w,w,6),f'negative|{layout}')
        check(br,E0,np.arange(w),f'empty rows|{layout}');check(br,np.arange(m),E0,f'empty cols|{layout}');check(br,E0,E0,f'both empty|{layout}')
        check(br,E0,np.array([w]),f'empty+invalid|{layout}');check(br,np.array([m]),E0,f'invalid+empty|{layout}');check(br,E0,np.array([-w-1]),f'empty+invalid neg|{layout}');check(br,np.array([-m-1]),E0,f'invalid neg+empty|{layout}')
        check(br,np.array([m]),np.arange(w),f'invalid rows|{layout}');check(br,np.arange(m),np.array([w]),f'invalid cols|{layout}');check(br,np.array([m]),np.array([w]),f'both invalid|{layout}')
        check(br,None,slice(0,w),f'None+slice|{layout}');check(br,None,None,f'None+None|{layout}');check(br,list(range(min(2,m))),np.arange(w),f'list|{layout}');check(br,r.random(m)<.5,np.arange(w),f'bool|{layout}')
        check(br,np.array([],np.int32),np.array([],np.uint32),f'both empty mixed|{layout}');check(br,np.array([[0]]),np.array([0]),f'2-D rows|{layout}');check(br,np.int64(0),np.arange(w),f'scalar row|{layout}')
    kk=int(r.integers(1,6));uu=r.standard_normal((m,kk))+0j;vv=r.standard_normal((kk,w))+0j
    check(row(uu,vv),r.integers(0,m,5),r.integers(0,w,5),'lowrank');check(row(uu,vv),E0,np.array([w]),'lowrank empty+invalid');check(row(uu,vv),None,slice(0,w),'lowrank slice')
out['mismatch_kinds']=dict(Counter(t.split('|')[0] for t in out['mismatches']));out['mismatches']=len(out['mismatches'])
print(json.dumps(out));json.dump(out,open('claude_production_gather_test.json','w'),indent=1)
