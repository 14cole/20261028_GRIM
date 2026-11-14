import os,sys,json,hashlib
from pathlib import Path
import numpy as np
sys.path.insert(0,os.environ['GRIM_ROOT']+'/tools/GHOST');sys.path.insert(0,'fmm')
from exact_validation import query_tiles,exact_rows
from build_pair_kernel import derive
from ghost_backend.compressed.hmatrix import QUERY_ENTRIES
records=[]
for n in [21845,21846,32768,65536,QUERY_ENTRIES,QUERY_ENTRIES+1]:
    parts=list(query_tiles(67,n));area=sum((r.stop-r.start)*(c.stop-c.start) for r,c in parts)
    assert area==67*n
    assert max((r.stop-r.start)*(c.stop-c.start) for r,c in parts)<=QUERY_ENTRIES
    # Exact sequential row and column coverage, including widths needing splits.
    for row in range(67):
        spans=[(c.start,c.stop) for r,c in parts if r.start<=row<r.stop]
        assert spans[0][0]==0 and spans[-1][1]==n
        assert all(a[1]==b[0] for a,b in zip(spans,spans[1:]))
    records.append(dict(unknowns=n,queries=len(parts),max_entries=max((r.stop-r.start)*(c.stop-c.start) for r,c in parts)))
class Oracle:
    def get(self,r,c):
        assert len(r)*len(c)<=QUERY_ENTRIES
        return r[:,None]+1j*c[None,:]
sample=np.array([4,17,2,99]);result,meta=exact_rows(Oracle(),sample,QUERY_ENTRIES+7)
assert np.array_equal(result.real,np.broadcast_to(sample[:,None],result.shape))
assert np.array_equal(result.imag,np.broadcast_to(np.arange(result.shape[1]),result.shape))
source=(Path(os.environ['GRIM_ROOT'])/'tools/GHOST/ghost_backend/twod/assembly/native/far.c').read_text()
original=(Path('accepted_paired_kernel.c')).read_text()
assert derive(source)==original
rejected=0
for token in ['/* Tile scatter','ghost_far_block_impl','int64_t plane = mb * nb;','for (int64_t j = 0; j < nb; ++j)','int64_t pair = i * nb + j;']:
    for changed in [source.replace(token,'changed',1),source+token]:
        # Duplicates after the scatter boundary are irrelevant to the derived
        # function, so test an inserted duplicate inside the retained prefix.
        if changed==source+token:changed=source.replace('/* Tile scatter',token+'\n/* Tile scatter',1)
        try:derive(changed)
        except ValueError:rejected+=1
        else:raise AssertionError(token)
Path('results/repairs.json').write_text(json.dumps(dict(queries=records,wide_query=meta,rejected_source_variants=rejected,generated_source_unchanged=True),indent=2))
