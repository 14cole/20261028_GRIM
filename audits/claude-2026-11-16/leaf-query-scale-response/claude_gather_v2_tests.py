"""Reviewer tests of gather v2, written before reading Codex's v2 tests."""
import os,sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST'))
from ghost_backend.compressed.hmatrix import BlockRow
import gather_v2;original,v2=gather_v2.install()
import query_hook  # v1 semantics, reimplemented locally to avoid double patching
def v1(self,rows=None,columns=None):
    if (self.v is None and isinstance(rows,np.ndarray) and isinstance(columns,np.ndarray) and rows.ndim==columns.ndim==1
            and np.issubdtype(rows.dtype,np.integer) and np.issubdtype(columns.dtype,np.integer)):
        return self.u[np.ix_(rows,columns)]
    return original(self,rows,columns)
r=np.random.default_rng(77);out=dict(cases=0,v2_mismatches=[],v1_mismatches=[])
def row(u,v=None):return BlockRow(0,0,u.shape[0],[(0,(u.shape[1] if v is None else v.shape[1]))],u,v)
def run(f,br,rows,cols):
    try:
        y=f(br,rows,cols);return ('ok',y.shape,str(y.dtype),y.tobytes())
    except Exception as e:return ('raise',type(e).__name__)
def check(br,rows,cols,tag):
    a=run(original,br,rows,cols);out['cases']+=1
    if run(v2,br,rows,cols)!=a:out['v2_mismatches'].append(tag)
    if run(v1,br,rows,cols)!=a:out['v1_mismatches'].append(tag)
E0=np.array([],np.int64)
for trial in range(300):
    m,w=int(r.integers(1,40)),int(r.integers(1,60));base=r.standard_normal((m,w))+1j*r.standard_normal((m,w))
    # special values
    flat=base.reshape(-1);k=min(flat.size,6)
    specials=[complex(-0.0,0.0),complex(0.0,-0.0),complex(np.inf,-np.inf),complex(np.nan,1.0),complex(float.fromhex('0x1p-1074'),0.0)]
    for i in range(min(k,len(specials))):flat[i]=specials[i]
    if flat.size>5:
        nanbits=np.array([0x7ff8000000000123],np.uint64).view(np.float64)[0];flat[5]=complex(nanbits,-nanbits)
    for layout,u in (('C',np.ascontiguousarray(base)),('F',np.asfortranarray(base)),('strided',np.repeat(np.repeat(base,2,0),2,1)[::2,::2])):
        br=row(u)
        for idt in (np.int64,np.int32,np.uint32):
            check(br,r.integers(0,m,int(r.integers(0,2*m))).astype(idt),r.integers(0,w,int(r.integers(0,2*w))).astype(idt),f'random|{layout}|{np.dtype(idt).name}')
        check(br,np.arange(m),np.arange(w),f'full|{layout}');check(br,r.integers(-m,m,4),r.integers(-w,w,6),f'negative|{layout}')
        check(br,E0,np.arange(w),f'empty rows + valid cols|{layout}');check(br,np.arange(m),E0,f'valid rows + empty cols|{layout}');check(br,E0,E0,f'both empty|{layout}')
        check(br,E0,np.array([w]),f'empty rows + invalid cols|{layout}');check(br,np.array([m]),E0,f'invalid rows + empty cols|{layout}')
        check(br,E0,np.array([-w-1]),f'empty rows + invalid negative cols|{layout}');check(br,np.array([-m-1]),E0,f'invalid negative rows + empty cols|{layout}')
        check(br,np.array([m]),np.arange(w),f'invalid rows + valid cols|{layout}');check(br,np.arange(m),np.array([w]),f'valid rows + invalid cols|{layout}')
        check(br,np.array([m]),np.array([w]),f'both invalid|{layout}')
        check(br,None,slice(0,w),f'None+slice|{layout}');check(br,list(range(min(2,m))),np.arange(w),f'list|{layout}');check(br,r.random(m)<.5,np.arange(w),f'bool|{layout}')
        check(br,np.array([],np.int32),np.array([],np.uint32),f'both empty mixed dtypes|{layout}')
    kk=int(r.integers(1,6));uu=r.standard_normal((m,kk))+0j;vv=r.standard_normal((kk,w))+0j
    check(row(uu,vv),r.integers(0,m,5),r.integers(0,w,5),'lowrank');check(row(uu,vv),E0,np.array([w]),'lowrank empty+invalid')
from collections import Counter
out['v2_mismatch_kinds']=dict(Counter(t.split('|')[0] for t in out['v2_mismatches']));out['v1_mismatch_kinds']=dict(Counter(t.split('|')[0] for t in out['v1_mismatches']))
out['v2_mismatches']=len(out['v2_mismatches']);out['v1_mismatches']=len(out['v1_mismatches'])
# what does the original do for the v1-mismatching cases?
br=row(np.zeros((4,5),complex));out['example_empty_rows_invalid_cols']=dict(original=run(original,br,E0,np.array([5]))[:2],v1=run(v1,br,E0,np.array([5]))[:2],v2=run(v2,br,E0,np.array([5]))[:2])
out['example_invalid_rows_empty_cols']=dict(original=run(original,br,np.array([4]),E0)[:2],v1=run(v1,br,np.array([4]),E0)[:2],v2=run(v2,br,np.array([4]),E0)[:2])
json.dump(out,open('claude_gather_v2_tests.json','w'),indent=1,default=str);print(json.dumps(out,indent=1,default=str))
