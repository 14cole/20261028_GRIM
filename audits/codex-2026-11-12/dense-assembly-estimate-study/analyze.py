"""Validate captured fields, forecasts and path coverage; emit portable summary."""
import hashlib,json,platform,sys
from pathlib import Path
import numpy as np,scipy
p=Path(__file__).resolve().parent
results={}
for file in sorted((p/'results').glob('*.json')):
    if file.name.endswith(('.metadata.json','.study.json')):continue
    d=json.loads(file.read_text()); name=file.stem
    study=json.loads((p/'results'/(name+'.npz.study.json')).read_text())
    assert d['backend_source_sha256']=='20dcfd39928d69775da0bc57d9a509c8cc649e9a70d2e3034fe9ffbcd0f022fb'
    if name=='d8000-refuse-1.3':
        assert d['error'].startswith('MemoryError:') and not study['assemblies']
    else:
        assert d['error'] is None,(name,d['error'])
        assert d['quality_gate']['passed'],name
        assert not d['quality_gate']['mesh_convergence_certified'],name
        assert d['rss_highwater_gib'] < d['options']['ram_budget_gib'],name
    plan=study['forecasts'][-1]['plan']
    results[name]=dict(wall_seconds=d['wall'],peak_sampled_gib=d['peak_gib'],
        peak_highwater_gib=d['rss_highwater_gib'],error=d['error'],
        actual_unknowns=d.get('actual_unknowns'),fields=d.get('fields_count'),
        forecast_gib=plan['peak_bytes']/2**30,phase_gib={k:v/2**30 for k,v in plan['phase_bytes'].items()},
        angle_batch=plan['angle_batch_size'],resources=study['resources'][0],
        fallback_calls=study['fallback_calls'],no_table_calls=study.get('no_table_calls',0),near_counts=[r['pairs'] for r in study['near']],
        candidate_used=any(x['breakdown'] is not None for x in study['forecasts']))
comparisons=[]
def compare(a,b,bitwise=False):
    x=np.load(p/'results'/(a+'.npz'))['field'];y=np.load(p/'results'/(b+'.npz'))['field']
    assert x.shape==y.shape and np.isfinite(x).all() and np.isfinite(y).all()
    relative=float(np.max(abs(x-y))/np.max(abs(x)))
    exact=bool(np.array_equal(x,y))
    if bitwise:assert exact,(a,b,relative)
    comparisons.append(dict(reference=a,candidate=b,fields=len(x),bitwise_equal=exact,
        relative_max_field_difference=relative))
for name in ('d8000','serial','near-rich','comb','numpy','numpy-medium','scipy-kernels','lossless','p2','p3'):
    compare(name+'-reference',name+'-candidate',True)
compare('d12000-reference','d12000-candidate')
compare('d12000-matched-batch','d12000-candidate',True)
compare('native-small','numpy-candidate',True)
compare('numpy-medium-reference','scipy-kernels-candidate')
compare('d8000-default','d8000-candidate')
for degree in (2,3):assert not results[f'p{degree}-candidate']['candidate_used']
assert results['numpy-medium-candidate']['fallback_calls']>0
assert results['scipy-kernels-candidate']['no_table_calls']>0
assert 3*16*4*max(results['comb-candidate']['near_counts'])>16*1024**2
for name,expected in (('alloc-fused',[[512,512]]),('alloc-unequal',[[512,512],[256,256]])):
    study=json.loads((p/'results'/(name+'.npz.study.json')).read_text())
    assert [r['shape'] for r in study['large_zeros']]==expected,(name,study['large_zeros'])
summary=dict(runtime_commit='ae08d66dc309c393ce62cc76bacd510a150ebf33',
    production_changed=False,prototype_scope='single dielectric P1; explicit tile 128; research only',
    python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,
    platform=platform.platform(),cases=len(results),results=results,comparisons=comparisons,
    limits=['Linux only; no Windows execution','No large-mesh NumPy fallback run; largest fallback is 2000 unknowns',
        'P2/P3 retain production forecast; these cases do not qualify a tighter polynomial estimate',
        'Survey solves validate the discrete systems, not mesh convergence',
        'Provisional workspace coefficients are not a proof of all-path memory bounds',
        'Times are single measurements; no statistical speedup claim'])
(p/'VALIDATION_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(dict(cases=len(results),comparisons=comparisons),indent=2))
