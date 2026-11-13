"""Research-only policies. None is imported by the production backend."""
import numpy as np

def install(spec,evidence):
 if 'dense_target' in spec:
  import inspect,textwrap
  from ghost_backend.linalg import dense
  target=float(spec['dense_target']);assert 0<target<=1e-12
  source=textwrap.dedent(inspect.getsource(dense.DenseFactor.solve)).replace('3e-15',repr(target))
  namespace=dict(dense.__dict__);exec(compile(source,'<audit dense target>','exec'),namespace)
  dense.DenseFactor.solve=namespace['solve'];evidence['dense_target']=target
 if spec.get('scaled_inverse'):
  from ghost_backend.compressed import hmatrix_factor as h
  Original=h.HMatrixSystem
  class ScaledOperator:
   def __init__(self,a):self.a=a;self.r=a.compression_rows[a.position];self.c=a.compression_columns[a.position]
   def __getattr__(self,name):return getattr(self.a,name)
   def _get(self,rows,cols,*args):return self.a._get(rows,cols,*args)*self.r[rows,None]*self.c[None,cols]
   def range_matmul(self,r0,r1,c0,c1,x,adjoint=False):
    r=self.a.compression_rows[r0:r1];c=self.a.compression_columns[c0:c1]
    if adjoint:return c[:,None]*self.a.range_matmul(r0,r1,c0,c1,x*r[:,None],True)
    return r[:,None]*self.a.range_matmul(r0,r1,c0,c1,x*c[:,None],False)
   def range_workspace_bytes(self,r0,r1,c0,c1,width,adjoint=False):return self.a.range_workspace_bytes(r0,r1,c0,c1,width,adjoint)+32*(r1-r0+c1-c0)*width
  class ScaledSystem(Original):
   def __init__(self,operator,*args,**kwargs):
    scaled=ScaledOperator(operator);self.r,self.c=scaled.r,scaled.c
    super().__init__(scaled,*args,**kwargs)
    self.evidence['scaled_inverse']=True
   def apply(self,b,solve=False,trans=0):
    assert solve,'Audit adapter only supports inverse actions'
    b=np.asarray(b);vector=b.ndim==1;left,right=(self.r,self.c) if trans==0 else (self.c,self.r)
    shape=slice(None) if vector else (slice(None),None)
    return super().apply(b*left[shape],True,trans)*right[shape]
  h.HMatrixSystem=ScaledSystem;evidence['scaled_inverse']=True
 if spec.get('inverse_float32'):
  from ghost_backend.compressed.hmatrix_factor import HMatrixSystem
  original=HMatrixSystem.__init__
  def init(self,*a,**kw):
   original(self,*a,**kw);saved=0;arrays=0
   def walk(node):
    nonlocal saved,arrays
    # Preserve leaf and Woodbury LU in complex128; reduce only low-rank
    # interpolation factors, with all physical residual checks unchanged.
    for name in ['e1','e2','v12','v21']:
     value=getattr(node,name,None)
     if isinstance(value,np.ndarray) and value.dtype==np.complex128:
      new=value.astype(np.complex64);setattr(node,name,new);saved+=value.nbytes-new.nbytes;arrays+=1
    if not node.leaf:walk(node.left);walk(node.right)
   walk(self.root);self.bytes-=saved;self.evidence.update(bytes=self.bytes,float32_saved_bytes=saved,float32_arrays=arrays)
  HMatrixSystem.__init__=init;evidence['inverse_float32']=True
