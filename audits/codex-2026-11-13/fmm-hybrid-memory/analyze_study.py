"""Recompute retained product, matrix-maximum and field errors; summarize paired measurements."""
import pathlib,json,numpy as np
D=pathlib.Path(__file__).parent;bench=[];systems=[];checks=0
for p in sorted(D.glob('*.json')):
 if p.name.endswith('-run.json') or p.name in ['SUMMARY.json','ENVIRONMENT.json','PARTITION_CHECK.json','SOURCE_IDENTITIES.json']:continue
 try:r=json.loads(p.read_text())
 except json.JSONDecodeError:continue
 if isinstance(r,dict) and 'product_seconds' in r and 'errors' in r:
  base=pathlib.Path(r['out']).name
  for kind,e in r['errors'].items():
   z=np.load(D/(base+'-'+kind+'.npz'));assert np.all(np.isfinite(z['actual']));truth=z['exact']
   if 'reference_rows' in z:np.testing.assert_allclose(z['reference_rows']@z['input'],truth,rtol=2e-13,atol=1e-25)
   error=float(np.max(abs(z['actual'][z['rows']]-truth))/np.max(abs(truth)));assert np.isclose(error,e['random_relative_max'],rtol=2e-8,atol=1e-25),(base,kind,error,e)
   if 'actual_matrix' in z:
    delta=z['actual_matrix']-z['reference_rows'];a=float(np.max(abs(delta))/np.max(abs(z['reference_rows'])));b=float(np.linalg.norm(delta)/np.linalg.norm(z['reference_rows']));assert np.isclose(a,e['matrix_relative_max'],rtol=2e-8,atol=1e-25);assert np.isclose(b,e['matrix_relative_fro'],rtol=2e-8,atol=1e-25)
   elif 'actual_columns' in z:
    delta=z['actual_columns']-z['reference_columns'];a=float(np.max(abs(delta))/np.max(abs(z['reference_columns'])));assert np.isclose(a,e['matrix_relative_max'],rtol=2e-8,atol=1e-25)
   if 'entry_actual' in z:assert np.isclose(np.max(abs(z['entry_actual']-z['entry_reference'])),e['entry_max_absolute'],rtol=2e-8,atol=1e-25)
   checks+=1
  q=dict(r);q['name']=base;q['median_product_seconds']={k:float(np.median(v)) for k,v in r['product_seconds'].items()}
  if 'hybrid' in q:
   h=dict(q['hybrid']);ranks=h.pop('ranks');h.update(rank_min=min(ranks or [0]),rank_max=max(ranks or [0]),rank_mean=float(np.mean(ranks)) if ranks else 0,rank_count=len(ranks));q['hybrid']=h
  bench.append(q)
 elif isinstance(r,dict) and 'dense_validation_live' in r:
  base=pathlib.Path(r['out']).name;ref=np.load(D/(base+'-reference.npy'))
  for v in r['results']:
   actual=np.load(D/(base+'-'+v['preconditioner']+'.npy'));err=float(np.max(abs(actual-ref))/np.max(abs(ref)));assert np.isclose(err,v['field_relative_max_error'],rtol=2e-8,atol=1e-25);checks+=1
  systems.append(dict(r,name=base))
pairs=[]
for n in [512,1024,2048]:
 group={r['mode']:r for r in bench if r['name'].startswith('scale-') and r['n']==n}
 if len(group)==3:
  a=group['cached'];pairs.append(dict(n=n,stream_peak_reduction=1-group['stream']['peak_before_reference_gib']/a['peak_before_reference_gib'],hybrid_peak_reduction=1-group['hybrid']['peak_before_reference_gib']/a['peak_before_reference_gib'],stream_retained_reduction=1-group['stream']['retained_bytes_partial']/a['retained_bytes_partial'],hybrid_retained_reduction=1-group['hybrid']['retained_bytes_partial']/a['retained_bytes_partial']))
vector_pairs=[]
for a in bench:
 if a['mode'] not in ['hybrid','hybrid_nodal','stream_sym']:continue
 candidates=[b for b in bench if b['mode']=='stream' and b['n']==a['n'] and b.get('shape','star')==a.get('shape','star') and b['k']==a['k']]
 if not candidates:continue
 b=candidates[0];differences={}
 for kind in ['S','K','KP','W']:
  u=np.load(D/(a['name']+'-'+kind+'.npz'));v=np.load(D/(b['name']+'-'+kind+'.npz'));assert np.array_equal(u['input'],v['input']);differences[kind]=float(np.max(abs(u['actual']-v['actual']))/np.max(abs(v['actual'])))
 vector_pairs.append(dict(candidate=a['name'],stream=b['name'],all_output_rows_random_difference=differences))
summary=dict(vector_pairs=vector_pairs,verified_comparisons=checks,benchmarks=bench,systems=systems,paired_scaling=pairs)
(D/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print('Verified',checks,'comparisons;',len(bench),'operator cases;',len(systems),'system cases');print(json.dumps(pairs,indent=2))
