"""Research-only: stop retaining the initial rank forecast as a sketch floor.
Optional initial_rank_cap limits the forecast, never the accepted matrix rank.
All tolerances, fresh probes and release gates are unchanged.
"""
from contextlib import contextmanager
import inspect
from ghost_backend.compressed import hmatrix as hm

@contextmanager
def adaptive_column_sketch(enabled, initial_rank_cap=None):
    if initial_rank_cap is not None and (not isinstance(initial_rank_cap,int) or initial_rank_cap<8):raise ValueError("Invalid initial rank forecast cap")
    stats=dict(enabled=bool(enabled),initial_rank_cap=initial_rank_cap,capped_calls=0,max_original_start_rank=0,max_effective_start_rank=0,selection_calls=0,reduced_selections=0,max_qr_rows_with_stale_floor=0,max_qr_rows_actual=0,examples=[])
    if not enabled:
        yield stats
        return
    original=hm.cross_approximation
    source=inspect.getsource(original)
    old='sketch = max(2*width, width + 64, int(1.5*start_rank) + 32)'
    assert source.count(old)==1,'Unexpected cross-approximation implementation'
    source=source.replace(old,'original_sketch = max(2*width, width + 64, int(1.5*start_rank) + 32)\n        sketch = original_sketch if skeleton is None else max(2*width, width + 64)')
    first='m, n = shape'
    assert source.count(first)==1
    source=source.replace(first,first+'\n    start_rank = _research_cap_forecast(start_rank)')
    marker='sample_rows = sum(len(value) for value in values)'
    assert source.count(marker)==1
    source=source.replace(marker,marker+'\n        _research_record_sketch(sample_rows, n, width, start_rank, original_sketch, sketch)')
    def cap_forecast(guess):
        effective=min(guess,initial_rank_cap) if initial_rank_cap is not None else guess
        stats['capped_calls']+=int(effective<guess)
        stats['max_original_start_rank']=max(stats['max_original_start_rank'],int(guess))
        stats['max_effective_start_rank']=max(stats['max_effective_start_rank'],int(effective))
        return effective
    def record(rows,n,width,guess,before,after):
        old_rows=before if rows>2*before else rows
        new_rows=after if rows>2*after else rows
        stats['selection_calls']+=1
        stats['max_qr_rows_with_stale_floor']=max(stats['max_qr_rows_with_stale_floor'],old_rows)
        stats['max_qr_rows_actual']=max(stats['max_qr_rows_actual'],new_rows)
        if new_rows<old_rows:
            stats['reduced_selections']+=1
            entry=dict(sample_rows=rows,columns=n,skeleton=width,initial_guess=guess,qr_rows_with_stale_floor=old_rows,qr_rows_actual=new_rows)
            stats['examples'].append(entry)
            stats['examples']=sorted(stats['examples'],key=lambda e:e['qr_rows_with_stale_floor']*e['columns'],reverse=True)[:12]
    namespace=dict(hm.__dict__,_research_record_sketch=record,_research_cap_forecast=cap_forecast)
    exec(compile(source,'<research adaptive column sketch>','exec'),namespace)
    hm.cross_approximation=namespace['cross_approximation']
    try:yield stats
    finally:hm.cross_approximation=original
