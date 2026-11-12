"""Verify declared production outcomes, actual fallback routes and full fields."""
import json,sys
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent;R=P/'results'
def read(name,suffix='.json'):return json.loads((R/(name+suffix)).read_text())
def compare(a,b):
    def keyed(name):
        return {(s['frequency_ghz'],s['theta_inc_deg'],s['polarization_internal']):complex(s['rcs_amp_real'],s['rcs_amp_imag']) for s in read(name,'.samples.json')}
    x,y=keyed(a),keyed(b);assert x.keys()==y.keys()
    keys=sorted(x);x=np.array([x[k] for k in keys]);y=np.array([y[k] for k in keys]);assert np.isfinite(y).all()
    error=float(max(abs(x-y))/max(abs(x)));assert error<1e-7,(a,b,error)
    return dict(reference=a,case=b,fields=len(x),relative_max_difference=error,bitwise_equal=bool(np.array_equal(x,y)))
rows=json.loads((P/'investigation-catalog.json').read_text());production=[]
for s in rows:
    if s['group']!='qualification':continue
    d=read(s['case']);expected=s['case']=='ownership-8000-memory-refusal'
    assert (d['error'] is not None)==expected,(s['case'],d['error'])
    if expected:assert d['error'].startswith('MemoryError:')
    else:assert d['quality_gate']['passed']
    production.append(dict(case=s['case'],expected_refusal=expected,passed=True))
fallback=[]
for s in rows:
    if not s.get('full_fallback'):continue
    d=read(s['case']);monitor=read(s['case'],'.monitor.json')
    assert d['fallback_calls']>0 and monitor['max_children']==0
    if s['case'].startswith('fallback-h-'):
        factors=read(s['case'],'.metadata.json')['compressed_factors']
        assert all(f['compressed']['operator']=='hmatrix' for f in factors)
    fallback.append(dict(**compare(s['reference_case'],s['case']),fallback_calls=d['fallback_calls']))
matched=compare('ownership-16000-matched-reference','ownership-16000-4.8-dense');assert matched['bitwise_equal']
automatic=[]
for name,expected in (('ownership-8000-1.8-automatic','compressed'),('ownership-8000-2.3-automatic','compressed'),('ownership-8000-2.3-disk-automatic','dense')):
    m=read(name,'.metadata.json')['backend_selection'];assert m['selected']==expected
    automatic.append(dict(case=name,selected=m['selected'],ranking=m['ranking'],dense_forecast_gib=m['dense_peak_gib']))
forced=compare('forced-h-fallback-False','forced-h-fallback-True')
fm=read('forced-h-fallback-True','.metadata.json');assert 'audit injected hierarchy assembly failure' in json.dumps(fm)
mm=read('magnetic-thin-compressed','.metadata.json');assert 'magnetic contrast' in json.dumps(mm)
magnetic=compare('magnetic-thin-dense','magnetic-thin-compressed')
result=dict(production=production,native_fallback=fallback,matched_dense_budget=matched,automatic=automatic,forced_hierarchy_fallback=forced,magnetic_thin_layer=magnetic)
(P/'VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n')
print('Validated',len(production),'production cases,',len(fallback),'complete native-fallback cases, and actual fallback routes.')
