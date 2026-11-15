"""Research: C-order residual copy, in-place LU in the owned F-order input."""
import numpy as np
def install():
    from ghost_backend.linalg.dense import DenseFactor
    from ghost_backend.linalg import residual_spool as spool
    from ghost_backend.linalg.refined_lu import requested_precision
    from ghost_backend.execution.metrics import timed_stage
    import ghost_backend.twod.solver as rcs
    restore=DenseFactor.restore_original
    def factor(self):
        if not self._owned_matrix or not self.a.flags.f_contiguous or not self.a.flags.owndata or not self.a.flags.writeable or requested_precision()!='double':
            raise ValueError('Layout prototype requires owned Fortran double matrix')
        from ghost_backend.execution.options import option
        if option('dense_residual_storage','auto')!='memory':raise ValueError('Layout prototype requires explicit RAM storage')
        self._sync_hierarchical_builds();self.mixed=None;self.hierarchical=None
        owned=self.a
        with spool._COPY_LOCK:
            spool.require_copy_capacity(owned.nbytes)
            saved=np.array(owned,order='C',copy=True)
        try:
            self.lu,self.piv=timed_stage('factorization')(rcs._SCIPY_LINALG.lu_factor)(self._scale_lu_buffer(owned),overwrite_a=True,check_finite=False)
        except BaseException:
            owned[:]=saved
            raise
        if not np.shares_memory(self.lu,owned):raise RuntimeError('LU unexpectedly allocated another matrix')
        self.a=saved;self._research_owned=owned
        self.event.update(residual_storage='research_row_major_memory',original_copy_bytes=saved.nbytes,lu_reuses_owned_buffer=True)
        self.event['factorizations']+=1
    def restored(self):
        if hasattr(self,'_research_owned'):
            source=getattr(self.a,'a',self.a)
            self._research_owned[:]=source
            self.event['research_restore_calls']=self.event.get('research_restore_calls',0)+1
        else:restore(self)
    DenseFactor._factor_double=factor;DenseFactor.restore_original=restored
