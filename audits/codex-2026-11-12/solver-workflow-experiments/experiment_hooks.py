"""Research hooks only. No production import, forecast discounts, or gate changes."""
import numpy as np
from contextlib import contextmanager

class ScaledMixed:
    def __init__(self,matrix):
        from ghost_backend.linalg.workspace import equilibrated_scaling_and_norm_1,strict_lu_factor,first_nonfinite
        self.matrix=np.asarray(matrix,dtype=complex);self.max_corrections=0
        self.row,self.col,_=equilibrated_scaling_and_norm_1(self.matrix)
        single=np.empty(self.matrix.shape,np.complex64,order='F')
        for j in range(0,len(matrix),128):single[:,j:j+128]=self.matrix[:,j:j+128]/self.row[:,None]/self.col[None,j:j+128]
        if first_nonfinite(single) is not None:raise np.linalg.LinAlgError('Nonfinite scaled single matrix')
        self.lu,self.piv=strict_lu_factor(single)
    def raw_solve(self,b,trans):
        from scipy.linalg import lu_solve
        left,right=(self.row,self.col) if trans==0 else (self.col,self.row)
        shape=(slice(None),None) if b.ndim==2 else slice(None)
        return lu_solve((self.lu,self.piv),(b/left[shape]).astype(np.complex64),trans=trans,check_finite=False).astype(complex)/right[shape]
    def solve(self,rhs,trans=0,return_residual=False):
        b=np.asarray(rhs,complex);x=self.raw_solve(b,trans);scale=np.maximum(np.max(abs(b),axis=0),1e-300);previous=float('inf')
        for step in range(10):
            applied=self.matrix@x if trans==0 else self.matrix.T@x if trans==1 else np.conj(self.matrix.T@np.conj(x))
            residual=b-applied;error=float(np.max(np.max(abs(residual),axis=0)/scale))
            if np.isfinite(error) and error<=2e-12:
                self.max_corrections=max(self.max_corrections,step)
                return (x,residual) if return_residual else x
            if not np.isfinite(error) or error>=previous*.98:raise np.linalg.LinAlgError('Scaled mixed refinement stalled')
            previous=error;x+=self.raw_solve(residual,trans)
        raise np.linalg.LinAlgError('Scaled mixed refinement exceeded correction limit')

@contextmanager
def installed(spec):
    from contextlib import ExitStack
    from unittest.mock import patch
    from ghost_backend.twod import solver as S
    from ghost_backend.linalg import refined_lu,residual_spool
    from ghost_backend.compressed import hmatrix_factor as HF,factor as CF
    records=[]
    with ExitStack() as stack:
        variant=spec.get('variant','baseline')
        if variant=='operator14':
            from ghost_backend.compressed.hmatrix import HMatrixOperator
            original_operator_init=HMatrixOperator.__init__
            def operator_init(self,*args,**kwargs):
                kwargs['tolerance']=min(kwargs.get('tolerance',1e-12),1e-14)
                original_operator_init(self,*args,**kwargs)
                records.append(dict(operator_tolerance=kwargs['tolerance'],purpose='scale-sensitivity diagnostic'))
            stack.enter_context(patch.object(HMatrixOperator,'__init__',operator_init))
        if variant=='schur':
            from schur_factor import SchurFactor
            from ghost_backend.linalg.dense import DenseFactor
            cache={}
            def factor(self):
                from ghost_backend.execution.dense_memory import current
                plan=current(len(self.a))
                if plan and plan['residual_storage']!='memory':raise MemoryError('Research Schur requires an admitted in-memory Dense plan')
                self.research_schur=SchurFactor(self.a,cache);self.event['factorizations']+=1
                entry=dict(common_blocks_reused=self.research_schur.reused,retained_factor_bytes=self.research_schur.retained_factor_bytes,shared_product_bytes=self.research_schur.shared_product_bytes)
                self.event['research_schur']=entry;records.append(entry)
            def condition(self):
                estimate=S._equilibrated_condition_from_lu(self.a,None,None,self.research_schur.solve,scaling=self._condition_scaling)
                self.diagnostics.update(condition_est=estimate,condition_method='research_schur_inverse',condition_label=self.label)
            def inverse(self,b,return_residual=False):
                x=self.research_schur.solve(b)
                return (x,None) if return_residual else x
            stack.enter_context(patch.object(DenseFactor,'_factor_double',factor));stack.enter_context(patch.object(DenseFactor,'_condition',condition));stack.enter_context(patch.object(DenseFactor,'_apply_inverse',inverse))
        if variant in ('fourier','sector7'):
            from fourier_factor import FourierFactor,SectorFourierFactor
            from ghost_backend.linalg.dense import DenseFactor
            old_inverse=DenseFactor._apply_inverse
            def factor(self):
                from ghost_backend.execution.dense_memory import current
                plan=current(len(self.a))
                if plan and plan['residual_storage']!='memory':raise MemoryError('Research Fourier requires an admitted in-memory Dense plan')
                self.research_fourier=(SectorFourierFactor(self.a,7) if variant=='sector7' else FourierFactor(self.a,2 if spec['material']=='diel' else 1))
                self.event['factorizations']+=1
                self.event['research_fourier']=dict(symmetry_error=self.research_fourier.symmetry_error,parts=getattr(self.research_fourier,'parts',None),sectors=getattr(self.research_fourier,'sectors',None),retained_bytes=getattr(self.research_fourier,'retained_bytes',None),all_entries_checked=True)
                records.append(self.event['research_fourier'])
            def condition(self):
                estimate=S._equilibrated_condition_from_lu(self.a,None,None,self.research_fourier.solve,scaling=self._condition_scaling)
                self.diagnostics.update(condition_est=estimate,condition_method='research_block_circulant_inverse',condition_label=self.label)
            def inverse(self,b,return_residual=False):
                x=self.research_fourier.solve(b)
                return (x,None) if return_residual else x
            stack.enter_context(patch.object(DenseFactor,'_factor_double',factor));stack.enter_context(patch.object(DenseFactor,'_condition',condition));stack.enter_context(patch.object(DenseFactor,'_apply_inverse',inverse))
        if variant in ('mixed','scaled_mixed'):
            stack.enter_context(refined_lu.linear_precision('mixed'))
            if variant=='scaled_mixed':stack.enter_context(patch.object(S,'RefinedLU',ScaledMixed))
        if variant=='disk_zstd':
            from lossless_spool import LosslessSpool
            class TrackedSpool(LosslessSpool):
                def __init__(self,*args,**kwargs):
                    super().__init__(*args,**kwargs);records.append(self.stats)
            stack.enter_context(patch.object(residual_spool,'ResidualSpool',TrackedSpool))
        elif variant.startswith('disk'):
            size=int(variant[4:]);stack.enter_context(patch.object(residual_spool.ResidualSpool,'block_bytes',size*1024**2))
        if variant=='compact':stack.enter_context(patch.object(CF,'PRECONDITIONER_TOLERANCE',1e-6))
        if variant in ('inverse32','inverse32_build','inverse32_fast'):
            if variant=='inverse32_fast':
                from ghost_backend.linalg.hierarchical import Node
                old_solve_into=Node.solve_into
                def single_solve(node,b,result,trans=0):
                    if node.lu is None or node.lu[0].dtype!=np.complex64:
                        return old_solve_into(node,b,result,trans)
                    if result.dtype==np.complex64:
                        return old_solve_into(node,np.asarray(b,np.complex64),result,trans)
                    tmp=np.empty(np.shape(b),np.complex64,order='F')
                    old_solve_into(node,np.asarray(b,np.complex64),tmp,trans)
                    result[...]=tmp
                stack.enter_context(patch.object(Node,'solve_into',single_solve))
            original=HF.HMatrixSystem.__init__;build0=HF.HMatrixSystem.build
            def quantize(node):
                saved=arrays=0
                for key,value in list(vars(node).items()):
                    if isinstance(value,np.ndarray) and value.dtype==np.complex128:
                        new=value.astype(np.complex64);saved+=value.nbytes-new.nbytes;arrays+=1;setattr(node,key,new)
                    elif key=='lu' and value is not None and value[0].dtype==np.complex128:
                        lu,piv=value;new=lu.astype(np.complex64);saved+=lu.nbytes-new.nbytes;arrays+=1;node.lu=(new,piv)
                return saved,arrays
            def build(self,*args,**kwargs):
                node=build0(self,*args,**kwargs);saved,arrays=quantize(node);self.bytes-=saved
                self.research_saved=getattr(self,'research_saved',0)+saved;self.research_arrays=getattr(self,'research_arrays',0)+arrays
                return node
            def create(self,*args,**kwargs):
                original(self,*args,**kwargs)
                if variant=='inverse32':
                    def walk(node):
                        saved,arrays=quantize(node)
                        if not node.leaf:
                            for child in (node.left,node.right):
                                s,a=walk(child);saved+=s;arrays+=a
                        return saved,arrays
                    saved,arrays=walk(self.root);self.bytes-=saved
                else:saved,arrays=self.research_saved,self.research_arrays
                entry=dict(original_equivalent_bytes=self.bytes+saved,retained_bytes=self.bytes,saved_bytes=saved,arrays=arrays,quantize_during_construction=variant!='inverse32',single_precision_products=variant=='inverse32_fast',retained_precision='complex64',operator_precision='complex128')
                self.evidence.update(bytes=self.bytes,research_inverse32=entry);records.append(entry)
            if variant!='inverse32':stack.enter_context(patch.object(HF.HMatrixSystem,'build',build))
            stack.enter_context(patch.object(HF.HMatrixSystem,'__init__',create))
        yield records
