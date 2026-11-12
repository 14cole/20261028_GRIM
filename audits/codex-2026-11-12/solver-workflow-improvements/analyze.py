"""Complete complex-field comparisons; timings are observations, not speed promises."""
import json,pathlib,numpy as np,statistics,os
D=pathlib.Path(os.environ.get('GRIM_EVIDENCE_DIR',pathlib.Path(__file__).parent))
results={}
for p in D.glob('*.json'):
 try:r=json.loads(p.read_text())
 except Exception:continue
 if isinstance(r,dict) and 'wall' in r and 'error' in r:results[p.stem]=r

def compare(a,b):
 x,y=np.load(D/(a+'.npy')),np.load(D/(b+'.npy'))
 if x.shape!=y.shape:raise ValueError((a,b,x.shape,y.shape))
 return dict(case=a,reference=b,relative_max=float(np.max(abs(x-y))/max(np.max(abs(y)),1e-300)),
             count=x.size,finite=bool(np.all(np.isfinite(x)) and np.all(np.isfinite(y))))
checks=[]
for name,r in results.items():
 if r['error'] is not None:continue
 if name.endswith('-compressed') and (D/(name[:-11]+'-dense.npy')).exists():
  checks.append(compare(name,name[:-11]+'-dense'))
for a,b in [('auto-cap-0.85','scale-diel-0.01-dense'),('auto-cap-1.0','scale-diel-0.01-dense'),
            ('auto-final-0.85','scale-diel-0.01-dense'),('auto-final-1.0','scale-diel-0.01-dense'),
            ('fallback-dense','native-dense'),('fallback-compressed','native-compressed'),('tile-0.01','native-dense')]:
 if (D/(a+'.npy')).exists() and (D/(b+'.npy')).exists():checks.append(compare(a,b))
for name in results:
 if name.startswith('experiment-') and (D/'experiment-control-0.npy').exists() and (D/(name+'.npy')).exists():
  checks.append(compare(name,'experiment-control-0'))
for group in ('pec','airfoil','diel'):
 for i in (0,1,'replacement'):
  a,b=f'bench-{group}-after-{i}',f'bench-{group}-before-{i}'
  if (D/(a+'.npy')).exists() and (D/(b+'.npy')).exists():checks.append(compare(a,b))
for label in ['sweep-profile','sweep-final']:
 if (D/(label+'.npy')).exists():
  x=np.load(D/(label+'.npy'))
  y=np.concatenate([np.load(D/(f'sweep-dense-{f}'+'.npy')) for f in [.98,1.,1.02]])
  checks.append(dict(case=label,reference='independent Dense frequency solves',relative_max=float(np.max(abs(x-y))/np.max(abs(y))),count=x.size,finite=bool(np.all(np.isfinite(x)))))
for a,b in [('coated-dense-refined','scale-coated-100-dense'),('scale-coated-0.01-dense','scale-coated-100-dense'),('tile-refined-0.01','native-dense'),('tile-100.0','native-dense'),('compression-only-final','scale-diel-0.01-dense')]:
 if (D/(a+'.npy')).exists():checks.append(compare(a,b))
for name in results:
 if name.startswith('bench-pec-') or name.startswith('experiment-'):
  checks.append(compare(name,'pec8k-dense'))
for radius in ['100','1','0.01']:
 checks.append(compare('scale-coated-'+radius+'-compressed','scale-coated-100-dense'))
summary=dict(successful=sum(r['error'] is None for r in results.values()),
 failures={n:r['error'] for n,r in results.items() if r['error'] is not None},
 checks=checks,quality_failures=[n for n,r in results.items() if r['error'] is None and not (r.get('quality_gate') or {}).get('passed')],
 measurements={n:{k:r.get(k) for k in ['wall','cpu','peak_rss_gib','stages','source_sha256']} for n,r in results.items()})
(D/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
for c in checks:print(c['case'],c['relative_max'])
print('successful',summary['successful'],'failures',summary['failures'],'quality_failures',summary['quality_failures'])
