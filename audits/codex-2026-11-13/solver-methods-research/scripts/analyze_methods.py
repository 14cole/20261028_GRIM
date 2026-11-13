import json,pathlib,numpy as np
D=pathlib.Path(__file__).parent
rows=[];comparisons=[]
for pattern in ['dense-*.json','scale-*.json','disk-*.json','inverse-*.json','holdout-*.json']:
 for p in sorted(D.glob(pattern)):
  if not p.stat().st_size:continue
  r=json.loads(p.read_text());m=r.get('metadata',{});events=m.get('compressed_factors',[])
  rows.append(dict(name=p.stem,wall=r.get('wall'),cpu=r.get('cpu'),peak_rss_gib=r.get('peak_rss_gib'),error=r.get('error'),quality_passed=r.get('quality_gate',{}).get('passed'),inverse_bytes=[e.get('preconditioners',[])[-1]['bytes'] for e in events if e.get('preconditioners')],factorizations=[e.get('factorizations') for e in events],refinement_steps=[e.get('refinement_steps') for e in events],scaled_errors=[s.get('event',{}).get('max_equilibrated_backward_error') for s in r.get('research',{}).get('dense_solves',[])],stages=r.get('stages')))
def compare(a,b,scale=1):
 pa,pb=D/(a+'.npy'),D/(b+'.npy')
 if pa.exists() and pb.exists():
  x=np.load(pa);y=np.load(pb)*scale
  comparisons.append(dict(reference=a,candidate=b,candidate_scale=scale,relative_max=float(np.max(abs(x-y))/np.max(abs(x))),bitwise=bool(np.array_equal(x,y))))
for body in ['diel','coated']:
 for rep in range(2):compare(f'dense-{body}-3e-15-{rep}',f'dense-{body}-1e-13-{rep}')
 for target in ['3e-15','1e-13','1e-12']:
  compare(f'scale-{body}-100.0-{target}',f'scale-{body}-0.01-{target}') # bare amplitude invariant at fixed electrical size
 for rad in ['0.01','100.0']:
  for target in ['1e-13','1e-12']:compare(f'scale-{body}-{rad}-3e-15',f'scale-{body}-{rad}-{target}')
 for policy in ['scaled','coarse','scaled-coarse','float32']:compare(f'inverse-{body}-control',f'inverse-{body}-{policy}')
for target in ['3e-15','1e-13']:compare(f'dense-diel-{target}-0',f'disk-diel-{target}')
for case in ['adjoint','lossless-star','thin-coating']:
 for policy in ['scaled','scaled-coarse','float32','coarse']:compare(f'holdout-{case}-control',f'holdout-{case}-{policy}')
result=dict(solves=rows,comparisons=comparisons)
(D/'METHODS_ANALYSIS.json').write_text(json.dumps(result,indent=2)+'\n')
for r in rows:print(r['name'],r['wall'],r['peak_rss_gib'],r['inverse_bytes'],r['factorizations'],r['refinement_steps'],r['error'])
print('comparisons');print(json.dumps(comparisons,indent=2))
