"""Research only: retain preconditioner operator blocks in complex64 at build time.
The accurate operator, exact validation rows and inverse arithmetic stay double.
This is scoped to one serial builder, never installed as a production policy.
"""
from contextlib import contextmanager
import numpy as np
from ghost_backend.compressed import hmatrix

@contextmanager
def packed_operator_blocks(enabled):
    base=hmatrix.BlockRow;stats=dict(enabled=bool(enabled),blocks=0,saved_bytes=0,near_overreservation=0)
    if not enabled:
        yield stats
        return
    def pack(value):
        if value is None:return None
        with np.errstate(over='raise',invalid='raise'):
            small=value.astype(np.complex64)
        if not np.all(np.isfinite(small)) or np.any((value!=0)&(small==0)):
            raise ValueError('Preconditioner block cannot be represented safely in complex64')
        stats['saved_bytes']+=value.nbytes-small.nbytes
        return small
    class PackedBlockRow(base):
        def __init__(self,row,start,stop,ranges,u,v,kind=0):
            before=stats['saved_bytes'];u=pack(u);v=pack(v)
            if kind==0:stats['near_overreservation']+=stats['saved_bytes']-before
            stats['blocks']+=1
            super().__init__(row,start,stop,ranges,u,v,kind)
    hmatrix.BlockRow=PackedBlockRow
    try:yield stats
    finally:hmatrix.BlockRow=base

def finish_operator(operator,stats):
    # Near blocks reserve 16 bytes/entry before construction. Far blocks use
    # BlockRow.nbytes after packing. Keep admission conservative during build,
    # then reconcile only that known near overreservation.
    excess=stats['near_overreservation']
    operator.bytes-=excess;operator.ledger.bytes-=excess
    operator.evidence['retained_bytes']=operator.bytes
    stats['operator_bytes']=operator.bytes
    stats['stored_block_bytes']=sum(row.nbytes for row in operator.near+operator.far+operator.dense_far)
    stats['admission_during_build']='conservative double-sized near reservation'
