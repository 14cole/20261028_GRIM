import numpy as np
from ghost_backend.execution.metrics import timed_stage
class LegacyNorms:
    def _absolute(self, row_scale=None, dimensionless=False):
            """Row sums/maxima and column sums/maxima of |H| (optionally row-scaled), one pass.
    
            Column partial sums are kept per fixed chunk of block rows and added
            in chunk order, so the result does not depend on the thread count.
            """
            n = self.n
            rows_sum, rows_max = np.zeros(n), np.zeros(n)
            chunks = {}
            def visit(row):
                a, b = row.start, row.stop
                width = max(1, (4*1024**2)//max(1, 16*(b - a)))
                local_sum, local_max = np.zeros(b - a), np.zeros(b - a)
                col_sum, col_max = np.zeros(len(row.columns)), np.zeros(len(row.columns))
                scale = None if row_scale is None else row_scale[a:b, None]
                for c0 in range(0, len(row.columns), width):
                    value = abs(row.values(None, slice(c0, c0 + width)))
                    if scale is not None:
                        value /= scale
                    if dimensionless:
                        value *= self.compression_rows[a:b, None]
                        value *= self.compression_columns[None, row.columns[c0:c0+width]]
                    local_sum += value.sum(axis=1); np.maximum(local_max, value.max(axis=1), out=local_max)
                    col_sum[c0:c0+width] = value.sum(axis=0); col_max[c0:c0+width] = value.max(axis=0)
                chunks[(row.kind, row.row)] = (row, local_sum, local_max, col_sum, col_max)
            self._passes(visit)
            cols_sum, cols_max = np.zeros(n), np.zeros(n)
            for key in sorted(chunks):
                row, local_sum, local_max, col_sum, col_max = chunks[key]
                rows_sum[row.start:row.stop] += local_sum
                np.maximum(rows_max[row.start:row.stop], local_max, out=rows_max[row.start:row.stop])
                np.add.at(cols_sum, row.columns, col_sum)
                np.maximum.at(cols_max, row.columns, col_max)
            return rows_sum, rows_max, cols_sum, cols_max
    def _norms(self):
            rows_sum, rows_max, cols_sum, _ = self._absolute()
            # Original (unpermuted) numbering, as the tile operator exposes it.
            self.row_norm = np.empty(self.n); self.row_norm[self.order] = rows_sum + self.near_tail
            self.row_max = np.empty(self.n); self.row_max[self.order] = rows_max
            self.column_norm = np.empty(self.n); self.column_norm[self.order] = cols_sum
            # Compression error is measured on sample rows, not bounded per row:
            # the residual gate of hmatrix_factor uses the exact sample rows.
            self.row_error = np.zeros(self.n); self.row_error[self.order] = self.near_tail
            self.column_error = np.zeros(self.n)
            if (np.all(self.compression_rows == self.compression_rows[0])
                    and np.all(self.compression_columns == self.compression_columns[0])):
                scale = self.compression_rows[0]*self.compression_columns[0]
                self.dimensionless_norms = (float(rows_sum.max()*scale), float(cols_sum.max()*scale))
            else:
                scaled_rows, _, scaled_columns, _ = self._absolute(dimensionless=True)
                self.dimensionless_norms = (float(scaled_rows.max()), float(scaled_columns.max()))
