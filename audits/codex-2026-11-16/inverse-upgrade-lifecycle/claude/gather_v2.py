"""Process-local equivalent of Codex's candidate-gather-v2.patch (transcribed from the patch)."""
import numpy as np
def install():
    from ghost_backend.compressed.hmatrix import BlockRow
    original=BlockRow.values
    def values(self,rows=None,columns=None):
        if (self.v is None and isinstance(rows,np.ndarray) and isinstance(columns,np.ndarray)
                and rows.ndim==columns.ndim==1 and rows.size and columns.size
                and np.issubdtype(rows.dtype,np.integer) and np.issubdtype(columns.dtype,np.integer)):
            return self.u[np.ix_(rows,columns)]
        return original(self,rows,columns)
    BlockRow.values=values;return original,values
