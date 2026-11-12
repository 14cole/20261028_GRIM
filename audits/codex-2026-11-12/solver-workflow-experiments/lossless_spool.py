"""Research-only checksummed byte-shuffled zstd residual spool.

All coefficients are restored bitwise. Compression workspace has not been
integrated into production admission; use only ample-budget study cases.
"""
import shutil,tempfile,time,weakref
import numpy as np
import zstandard as zstd
from ghost_backend.linalg.residual_spool import ResidualSpool
class LosslessSpool(ResidualSpool):
    def __init__(self,matrix,directory,checkpoint):
        if matrix.dtype!=np.complex128 or matrix.ndim!=2:raise ValueError('Complex128 matrix required')
        self.shape,self.dtype,self.ndim=matrix.shape,matrix.dtype,2;self.checkpoint=checkpoint
        if shutil.disk_usage(directory).free<matrix.nbytes+64*1024**2:raise OSError('Not enough scratch for worst case compressed spool')
        self.file=tempfile.TemporaryFile(prefix='ghost-research-zstd-',dir=directory);self._cleanup=weakref.finalize(self,self.file.close)
        self.records=[];self.stats=dict(original_bytes=matrix.nbytes,compressed_bytes=0,write_seconds=0.,read_seconds=0.,products=0,codec='zstd1-byte-shuffle-checksum',workspace_accounting='research only; no production admission discount')
        t=time.perf_counter();encoder=zstd.ZstdCompressor(level=1,write_checksum=True)
        try:
            for start,stop in self._rows():
                checkpoint();block=np.ascontiguousarray(matrix[start:stop]);raw=block.view(np.uint8).reshape(-1,8).T.copy().tobytes();encoded=encoder.compress(raw)
                self.records.append((self.file.tell(),len(encoded),start,stop));self.file.write(encoded);self.stats['compressed_bytes']+=len(encoded)
            self.file.flush()
        except BaseException:self.close();raise
        self.stats['write_seconds']=time.perf_counter()-t
    def blocks(self):
        decoder=zstd.ZstdDecompressor()
        for offset,size,start,stop in self.records:
            self.checkpoint();t=time.perf_counter();self.file.seek(offset);encoded=self.file.read(size)
            if len(encoded)!=size:raise OSError('Truncated compressed residual spool')
            raw=decoder.decompress(encoded,max_output_size=(stop-start)*self.shape[1]*16)
            if len(raw)!=(stop-start)*self.shape[1]*16:raise OSError('Wrong decompressed block size')
            block=np.frombuffer(raw,np.uint8).reshape(8,-1).T.copy().ravel().view(np.complex128).reshape(stop-start,self.shape[1])
            self.stats['read_seconds']+=time.perf_counter()-t
            yield start,stop,block
    def __matmul__(self,rhs):
        rhs=np.asarray(rhs);vector=rhs.ndim==1
        if vector:rhs=rhs[:,None]
        if rhs.ndim!=2 or rhs.shape[0]!=self.shape[1]:raise ValueError('Invalid residual RHS')
        out=np.empty((self.shape[0],rhs.shape[1]),complex)
        for start,stop,block in self.blocks():out[start:stop]=block@rhs
        self.stats['products']+=1
        return out[:,0] if vector else out
    def restore_into(self,matrix):
        for start,stop,block in self.blocks():matrix[start:stop]=block
