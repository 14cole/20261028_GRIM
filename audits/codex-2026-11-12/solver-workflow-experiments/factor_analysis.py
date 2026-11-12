import json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent;rows=[]
for f in sorted((P/'factor_results').glob('*.json')):
 r=json.loads(f.read_text());row=dict(r)
 if r.get('error') is None:
  baseline=P/'factor_results'/(Path(r['source']).stem+'-dense.npz')
  if not baseline.exists():baseline=P/'factor_results'/(Path(r['source']).stem+'-dense_refined.npz')
  if baseline.exists():
   x=np.load(f.with_suffix('.npz'))['solution'];y=np.load(baseline)['solution'];assert x.shape==y.shape and np.isfinite(x).all()
   row['comparison_reference']=baseline.name;row['relative_max_norm_vs_dense']=float(np.max(abs(x-y))/np.max(abs(y)))
  else:row['comparison_reference']=None;row['relative_max_norm_vs_dense']=None
  row['max_backward_error']=max(v['backward_error'] for v in r['metrics']);assert row['max_backward_error']<=1e-12
 rows.append(row)
(P/'FACTOR_SUMMARY.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n')
for r in rows:print(r['source'],r['variant'],r.get('factor_seconds_including_input_read'),r.get('peak_rss_gib'),r.get('relative_max_norm_vs_dense'),r['error'])
