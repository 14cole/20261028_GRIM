import json,sys,tempfile
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(sys.argv[1])/'tools/GHOST'))
from lossless_spool import LosslessSpool
rng=np.random.default_rng(33);a=np.asfortranarray(rng.normal(size=(257,257))+1j*rng.normal(size=(257,257)));a[0,0]=complex(-0.,0.);rhs=rng.normal(size=(257,5))+1j*rng.normal(size=(257,5))
# Force several blocks and a short final block for the bitwise/storage checks.
LosslessSpool.block_bytes=64*257*16
with tempfile.TemporaryDirectory() as d:
 s=LosslessSpool(a,d,lambda:None);assert len(s.records)>1;restored=np.empty_like(a);s.restore_into(restored)
 assert a.tobytes(order='F')==restored.tobytes(order='F')
 assert np.allclose(s@rhs,a@rhs,rtol=1e-13,atol=1e-12)
 offset,size,_,_=s.records[0];s.file.seek(offset+size//2);byte=s.file.read(1);s.file.seek(offset+size//2);s.file.write(bytes([byte[0]^1]));s.file.flush()
 try:s@rhs
 except Exception as e:rejected=type(e).__name__
 else:raise AssertionError('Corrupt spool accepted')
 s.close()
 s=LosslessSpool(a,d,lambda:None)
 assert np.allclose(s@rhs[:,0],a@rhs[:,0],rtol=1e-13,atol=1e-12)
 s.file.truncate(s.stats['compressed_bytes']-1)
 try:s@rhs
 except OSError:truncated=True
 else:raise AssertionError('Truncated spool accepted')
 s.close()
Path(__file__).with_name('LOSSLESS_CONTROLS.json').write_text(json.dumps(dict(bitwise_roundtrip=True,matmul=True,corruption_rejected=rejected,truncation_rejected=truncated,vector_product=True,multiple_blocks_with_short_tail=True),indent=2)+'\n');print('Lossless spool controls passed')
