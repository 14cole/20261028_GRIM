"""Cross-check pinned reviewer hashes/arrays against our preserved 32k results."""
import os,json,hashlib,statistics
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent;C=ROOT/'claude';prior=Path(os.environ['PRIOR_RESULTS'])
digest=lambda a:hashlib.sha256(a.tobytes()).hexdigest()
cache={}
def arrays(label):
    if label not in cache:
        with np.load(prior/(label+'-batch0000.npz')) as z:cache[label]={k:z[k] for k in z.files}
    return cache[label]
out={};hash_checks=field_checks=0
for idx,folder in [('array_hashes_cap2900.json','results'),('evidence_32k/array_hashes.json','evidence_32k')]:
    for label,entry in json.loads((C/idx).read_text()).items():
        mode='cap2900-production' if label.startswith('l-') and 'production' in label else 'cap2900-sequential'
        source=arrays(mode);checks={}
        for key,meta in entry.items():
            a=source[key];assert list(a.shape)==meta['shape']
            if 'dtype' in meta:assert str(a.dtype)==meta['dtype']
            assert digest(a)==meta['sha256_c_order'],(label,key)
            checks[key]=True;hash_checks+=1
        small=C/folder/(label+'-fields-and-rows.npz')
        with np.load(small) as z:
            for key in z.files:
                expected=source['rhs'][source['rows']] if key=='rhs_rows' else source[key]
                assert expected.shape==z[key].shape and expected.dtype==z[key].dtype and expected.tobytes()==z[key].tobytes(),(label,key)
                field_checks+=1
        out[label]=dict(source=mode,full_array_hash_checks=checks,small_arrays_bit_identical=True)
rows=[]
for label,_ in json.loads((C/'claude_L.json').read_text()):
    d=json.loads((C/'results'/(label+'.json')).read_text());h=json.loads((C/'results'/(label+'.hooks.json')).read_text());t=json.loads((C/'results'/(label+'.time.json')).read_text())
    assert t['returncode']==0
    rows.append(dict(label=label,compute_seconds=d['compute_seconds'],solve_seconds=d['solve_seconds'],peak_gib=d['peak_gib'],builds=h['builds'],gmres_columns=d['event']['gmres_columns'],corrections=h['inverse_calls'][0]['corrections']))
p=[r['compute_seconds'] for r in rows if 'production' in r['label']];s=[r['compute_seconds'] for r in rows if 'sequential' in r['label']]
assert max(s)<min(p)
summary=dict(hash_checks=hash_checks,small_array_checks=field_checks,comparisons=out,timing_rows=rows,
    median_compute_reduction=1-statistics.median(s)/statistics.median(p),
    clean_production3_vs_sequential_median=1-statistics.median(s)/p[-1],
    caveat='production-0 overlaps evidence hashing/checking; no new 32k solve in this response. Full arrays freshly rehashed locally; old density-parts reconstruction script not rerun.')
(ROOT/'review-evidence-check.json').write_text(json.dumps(summary,indent=2));print(json.dumps({k:v for k,v in summary.items() if k!='comparisons'},indent=2))
