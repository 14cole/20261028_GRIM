"""Rank-direction conversion check, supplementary to the original global bound."""
import numpy as np
from codex_hooks import convert,CHUNK
def convert_factor(a,key):
    small,record=convert(a)
    if small is a:return small,record
    # e = A_child^-1 U carries rank in columns; V carries rank in rows.
    if key not in ('e1','e2','v12','v21'):raise ValueError(key)
    vectors=a.T if key.startswith('e') else a
    rounded=small.T if key.startswith('e') else small
    worst=0.
    for x,y in zip(vectors,rounded):
        scale=error=0.
        for start in range(0,x.size,CHUNK):
            xx=x[start:start+CHUNK];yy=y[start:start+CHUNK]
            for before,after in ((xx.real,yy.real),(xx.imag,yy.imag)):
                scale=max(scale,float(np.max(abs(before),initial=0.)))
                error=max(error,float(np.max(abs(before-after),initial=0.)))
        worst=max(worst,error/scale if scale else 0.)
    accepted=worst<=np.finfo(np.float32).eps
    record.update(rank_direction='columns' if key.startswith('e') else 'rows',
        rank_vector_max_relative_error=worst,accepted=bool(accepted))
    if not accepted:record['reason']='retain double: rank-vector conversion exceeds bound'
    return (small if accepted else a),record
