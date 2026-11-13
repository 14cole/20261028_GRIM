"""Recompute every comparison from full complex arrays. No accuracy labels for timing deltas."""
import json,pathlib,os,numpy as np,statistics
D=pathlib.Path(os.environ.get('GRIM_EVIDENCE_DIR',pathlib.Path(__file__).parent))
results={}
for p in D.glob('*.json'):
 try:r=json.loads(p.read_text())
 except Exception:continue
 if isinstance(r,dict) and 'wall' in r and 'error' in r:results[p.stem]=r
checks=[]
def compare(a,b):
 if not (D/(a+'.npy')).exists() or not (D/(b+'.npy')).exists():return
 x,y=np.load(D/(a+'.npy')),np.load(D/(b+'.npy'))
 assert x.shape==y.shape,(a,b,x.shape,y.shape)
 checks.append(dict(case=a,reference=b,relative_max=float(np.max(abs(x-y))/max(float(np.max(abs(y))),1e-300)),count=x.size,finite=bool(np.isfinite(x).all() and np.isfinite(y).all())))
for n in results:
 if n.endswith('-compressed'):compare(n,n[:-11]+'-dense')
for body in ['diel','coated','thin']:
 for mode in ['dense','compressed']:
  compare(f'final-{body}-0.01-{mode}',f'final-{body}-100.0-dense')
compare('holdout-thin-large-before','final-thin-large-dense')
compare('holdout-thin-large-after','final-thin-large-dense')
compare('final-coat-disk','final-coated-0.01-dense')
compare('final-workers','final-fallback-dense')
compare('prior_reference/tile-0.01','final-fallback-dense')
compare('dense-coat-small','dense-coat-large')
compare('prior_reference/scale-coated-0.01-dense','prior_reference/scale-coated-100-dense')
compare('final-coated-0.01-dense','prior_reference/scale-coated-100-dense')
compare('final-coated-100.0-dense','prior_reference/scale-coated-100-dense')
for n in results:
 if n.startswith('final-diel8k-after-'):compare(n,n.replace('-after-','-before-'))
 if n.startswith('holdout-') and n.endswith('-after'):compare(n,n[:-6]+'-before')
 if n.startswith('diel8k-probe-') or n.startswith('diel8k-tight-'):compare(n,n.replace('-probe-','-before-').replace('-tight-','-before-'))
for cap in ['0.85','1.0']:
 compare('final-auto-'+cap,'final-diel-0.01-dense')
 compare('final-auto-single-'+cap,'final-diel-0.01-dense')
# Complete matrices of reported measurements retain the final gates and source identity.
measurements={}
for n,r in results.items():
 metrics=(r.get('metadata',{}).get('runtime_profile') or {})
 measurements[n]={k:r.get(k) for k in ['wall','cpu','peak_rss_gib','source_sha256','stages']}
 measurements[n]['stage_calls']=metrics.get('stage_calls',{})
 measurements[n]['condition_est_max']=r.get('metadata',{}).get('condition_est_max')
 measurements[n]['mesh_convergence_certified']=r.get('metadata',{}).get('mesh_convergence_certified',(r.get('quality_gate') or {}).get('mesh_convergence_certified'))
summary=dict(successful=sum(r['error'] is None for r in results.values()),runtime_errors={n:r['error'] for n,r in results.items() if r['error'] is not None},quality_failures=[n for n,r in results.items() if r['error'] is None and not(r.get('quality_gate') or {}).get('passed')],checks=checks,measurements=measurements)
(D/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
print('successful',summary['successful'],'errors',summary['runtime_errors'],'gate failures',summary['quality_failures'])
for c in checks:print(c['case'],c['reference'],c['relative_max'])
