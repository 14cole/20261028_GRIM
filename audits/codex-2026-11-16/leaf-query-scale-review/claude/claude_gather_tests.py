"""Reviewer tests of the dense gather patch and of the leaf-query workspace rule.
Written before reading Codex's check_query.py / check_full_query.py."""
import os,sys,json,tracemalloc
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST'))
from ghost_backend.compressed.hmatrix import BlockRow
original=BlockRow.values
import query_hook;query_hook.install();patched=BlockRow.values
assert patched is not original
r=np.random.default_rng(2026);out=dict(value_cases=0,mismatches=[],flag_differences={},path_checks=[])
def flags(a):return (bool(a.flags.c_contiguous),bool(a.flags.f_contiguous),bool(a.flags.owndata),bool(a.flags.writeable))
def row(u,v=None):return BlockRow(0,0,u.shape[0],[(0,(u.shape[1] if v is None else v.shape[1]))],u,v)
def compare(br,rows,cols,tag):
    a=original(br,rows,cols);b=patched(br,rows,cols);out['value_cases']+=1
    ok=a.shape==b.shape and a.dtype==b.dtype and np.array_equal(a,b)
    if not ok:out['mismatches'].append(tag)
    if flags(a)!=flags(b):
        e=out['flag_differences'].setdefault(tag.split('|')[0],dict(count=0,example=None));e['count']+=1;e['example']=dict(original=flags(a),patched=flags(b),shape=list(a.shape))
    return a,b
for trial in range(400):
    m,w=int(r.integers(1,60)),int(r.integers(1,90));dt=r.choice([np.complex128,np.complex64,np.float64])
    base=(r.standard_normal((m,w))+1j*r.standard_normal((m,w))).astype(dt)
    for layout,u in (('C',np.ascontiguousarray(base)),('F',np.asfortranarray(base)),('strided',np.repeat(np.repeat(base,2,0),2,1)[::2,::2])):
        for idt in (np.int64,np.int32,np.uint32,np.intp):
            nr,nc=int(r.integers(0,2*m)),int(r.integers(0,2*w))
            rows=r.integers(0,m,nr).astype(idt);cols=r.integers(0,w,nc).astype(idt)
            compare(row(u),rows,cols,f'dense int arrays|{layout}|{np.dtype(idt).name}|{np.dtype(dt).name}')
        rows=r.integers(-m,m,5);cols=r.integers(-w,w,7);compare(row(u),rows,cols,f'dense negative indices|{layout}')
        compare(row(u),np.arange(m),np.arange(w),f'dense full aranges|{layout}')
        compare(row(u),np.sort(r.integers(0,m,m)),np.sort(r.integers(0,w,w)),f'dense sorted repeats|{layout}')
        # selectors that must keep the original path
        compare(row(u),None,slice(0,max(1,w//2)),f'None+slice|{layout}');compare(row(u),None,None,f'None+None|{layout}')
        compare(row(u),list(range(min(3,m))),np.arange(w),f'list rows|{layout}');compare(row(u),r.random(m)<.5,np.arange(w),f'bool rows|{layout}')
        compare(row(u),np.arange(m),r.random(w)<.5,f'bool cols|{layout}');compare(row(u),np.arange(m),slice(None),f'array+slice|{layout}')
    # low rank path untouched
    k=int(r.integers(1,8));uu=r.standard_normal((m,k))+1j*r.standard_normal((m,k));vv=r.standard_normal((k,w))+1j*r.standard_normal((k,w))
    compare(row(uu,vv),r.integers(0,m,6),r.integers(0,w,9),'lowrank int arrays');compare(row(uu,vv),None,slice(0,w),'lowrank None+slice')
# out-of-range behaviour identical (both raise)
u=np.zeros((4,5),complex)
for rows,cols in ((np.array([4]),np.array([0])),(np.array([0]),np.array([5]))):
    res=[]
    for f in (original,patched):
        try:f(row(u),rows,cols);res.append('no error')
        except IndexError:res.append('IndexError')
    out['path_checks'].append(dict(case='out of range',original=res[0],patched=res[1]))
# 2-D index arrays keep the original path
a,b=compare(row(np.arange(20.).reshape(4,5)+0j),np.array([[0,1]]),np.array([0,1]),'2-D row index (original path; second selector indexes the new axis)')
# allocation: wide partner row
def peak(f,*a):
    tracemalloc.start();tracemalloc.reset_peak();b0=tracemalloc.get_traced_memory()[0];y=f(*a);p=tracemalloc.get_traced_memory()[1]-b0;tracemalloc.stop();return p,y
alloc=[]
for width in (512,4096,32768):
    u=np.ones((256,width),complex);br=row(u);rows=np.arange(149);cols=np.arange(0,149)
    p0,_=peak(original,br,rows,cols);p1,_=peak(patched,br,rows,cols);alloc.append(dict(partner_columns=width,query=149,original_MiB=p0/2**20,patched_MiB=p1/2**20,result_MiB=149*149*16/2**20))
out['gather_allocation']=alloc
# workspace of a low-rank contribution relative to q
low=[]
for q,rank in ((149,32),(149,149),(149,600),(149,2000),(256,159),(256,384)):
    uu=np.ones((q,rank),complex);vv=np.ones((rank,q),complex);br=row(uu,vv);rows=np.arange(q);cols=np.arange(q);res=np.zeros((q,q),complex)
    def query():
        res[np.ix_(rows,cols)]+=patched(br,rows,cols)
    tracemalloc.start();b0=tracemalloc.get_traced_memory()[0];tracemalloc.reset_peak();query();p=tracemalloc.get_traced_memory()[1]-b0;tracemalloc.stop()
    qb=q*q*16;low.append(dict(query_side=q,rank=rank,peak_excluding_result_MiB=p/2**20,peak_including_result_MiB=(p+qb)/2**20,two_q_MiB=2*qb/2**20,four_q_plus_1_MiB=(4*qb+2**20)/2**20,exceeds_4q_plus_1=bool(p+qb>4*qb+2**20)))
out['lowrank_contribution_workspace']=low
json.dump(out,open('claude_gather_tests.json','w'),indent=1)
print('value cases',out['value_cases'],'mismatches',len(out['mismatches']));print('flag differences',json.dumps(out['flag_differences']));print(out['path_checks']);[print(x) for x in alloc];[print(x) for x in low]
