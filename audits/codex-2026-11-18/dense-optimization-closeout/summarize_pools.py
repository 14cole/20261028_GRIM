"""Summarize the saved unmodified pool controls; no timing rerun."""
import json,pathlib,math
r=pathlib.Path(__file__).resolve().parent
out={}
for key,np_threads in [('4-4',4),('1-4',1)]:
    d=json.loads((r/f'fresh-pools-{key}.json').read_text())
    assert d['n']==4146 and d['pools_read_back']==d['requested']=={'numpy':np_threads,'scipy':4}
    assert len(d['results'])==9
    assert all(math.isfinite(v) and v>0 for x in d['results'].values() for v in x.values())
    times={k:v['total'] for k,v in d['results'].items()}
    out[key]={'times':times,'scipy_inverse_mixed_over_same':times['scipy_gemm_inverse|numpy_old']/times['scipy_gemm_inverse|scipy_zgemm'],'numpy_inverse_mixed_over_same_F':times['numpy_gemm_inverse|scipy_zgemm']/times['numpy_gemm_inverse|numpy_F'],'lu_direct_change_percent':100*(times['scipy_lu|scipy_zgemm']/times['scipy_lu|numpy_old']-1)}
(r/'pool-summary.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
