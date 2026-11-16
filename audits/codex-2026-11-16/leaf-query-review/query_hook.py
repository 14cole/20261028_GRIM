"""Process-local dense BlockRow gather prototype. Production files unchanged."""
import numpy as np
def install(price_leaves=False):
    from ghost_backend.compressed.hmatrix import BlockRow
    original=BlockRow.values
    def values(self,rows=None,columns=None):
        if (self.v is None and isinstance(rows,np.ndarray) and isinstance(columns,np.ndarray)
                and rows.ndim==columns.ndim==1
                and np.issubdtype(rows.dtype,np.integer) and np.issubdtype(columns.dtype,np.integer)):
            return self.u[np.ix_(rows,columns)]
        return original(self,rows,columns)
    BlockRow.values=values

    if price_leaves:
        from ghost_backend.compressed.hmatrix_factor import HMatrixSystem
        from ghost_backend.compressed.hmatrix import HMatrixOperator
        from ghost_backend.compressed.construction import Construction
        step0=Construction.step
        def step(self,label,additional,*live):
            # Only aligned inverse diagonal queries into HMatrixOperator.
            # Existing call prices 2*q. Direct selection can hold result,
            # advanced-index destination and contribution together; use 4*q
            # plus an explicit index/Python-workspace allowance.
            if label=='leaf coefficients' and isinstance(self.owner,HMatrixSystem) and isinstance(self.owner.operator,HMatrixOperator):
                additional=2*int(additional)+1024**2
            return step0(self,label,additional,*live)
        Construction.step=step
