"""Reviewer copy of hooks.py: underflow to zero is recorded, not rejected."""
"""Process-local experiments. Never changes production files or accuracy gates."""
import time,resource
import numpy as np
RECORD={'packing':[],'residual_products':[]}
def memory():
    from pathlib import Path
    d={line.split(':')[0]:line.split(':')[1].strip() for line in Path('/proc/self/status').read_text().splitlines() if ':' in line}
    return dict(rss_bytes=int(d['VmRSS'].split()[0])*1024,peak_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20)
def install(spec):
    from ghost_backend.compressed.hmatrix_factor import HMatrixSystem
    from ghost_backend.linalg.dense import DenseFactor
    packing=spec.get('packing','none')
    def pack(self,node):
        if node.leaf:return
        saved=0
        for key in ('v12','v21','e1','e2'):
            a=getattr(node,key)
            if a.dtype!=np.complex128:continue
            with self.construction.step('research inverse packing',2*a.nbytes):
                small=a.astype(np.complex64)
                lost=(a!=0)&(small==0)
                if not np.isfinite(small).all():raise FloatingPointError('Unsafe research packing: nonfinite')
                if lost.any():RECORD.setdefault('underflow',[]).append(dict(n=node.n,key=key,count=int(lost.sum()),entries=int(a.size),max_lost_abs=float(np.abs(a[lost]).max()),array_max_abs=float(np.abs(a).max()),array_fro=float(np.linalg.norm(a))))
                delta=a.nbytes-small.nbytes;setattr(node,key,small);self.bytes-=delta;saved+=delta
        RECORD['packing'].append(dict(n=node.n,saved_bytes=saved,accounted_bytes=self.bytes,**memory()))
    if packing=='construction':
        original=HMatrixSystem.build
        def build(self,*args,**kwargs):
            node=original(self,*args,**kwargs);pack(self,node);return node
        HMatrixSystem.build=build
    elif packing=='post':
        original=HMatrixSystem.__init__
        def init(self,*args,**kwargs):
            original(self,*args,**kwargs)
            def walk(node):
                if not node.leaf:walk(node.left);walk(node.right);pack(self,node)
            walk(self.root);self.evidence['bytes']=self.bytes
        HMatrixSystem.__init__=init
    elif packing!='none':raise ValueError(packing)
    mode=spec.get('residual','full')
    if mode!='full':
        original=DenseFactor.__init__
        class Rows:
            def __init__(self,a):self.a=a;self.shape=a.shape;self.dtype=a.dtype;self.nbytes=a.nbytes
            def __len__(self):return len(self.a)
            def __matmul__(self,x):
                t=time.perf_counter();out=np.empty((len(self.a),)+x.shape[1:],complex,order='F' if mode=='full_f_output' else 'C');width=spec.get('row_block',256)
                if mode=='full_f_output':np.matmul(self.a,x,out=out)
                else:
                    for start in range(0,len(self.a),width):
                        block=self.a[start:start+width]
                        if mode=='blocked_c':block=np.ascontiguousarray(block)
                        out[start:start+width]=block@x
                RECORD['residual_products'].append(dict(seconds=time.perf_counter()-t,rhs=x.shape[-1] if x.ndim==2 else 1,mode=mode,**memory()))
                return out
        def init(self,*args,**kwargs):
            original(self,*args,**kwargs)
            if self.mixed is not None or self.hierarchical is not None or self._residual_spool is not None:raise ValueError('Row prototype requires RAM double LU')
            self.a=Rows(self.a)
        DenseFactor.__init__=init
