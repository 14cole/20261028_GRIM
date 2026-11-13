import pathlib,json,numpy as np
D=pathlib.Path(__file__).parent;load=lambda n:json.loads((D/n).read_text());summary={}
claude={x['case']:x for x in map(json.loads,(D/'claude_reference/operator_checks.jsonl').read_text().splitlines())}
summary['matrix_checks']=[]
for case in ['two-circles-gap-1e-4','level-transition-3-4b','square-graded']:
 r=load(case+'.json')
 for kind,z in r['results'].items():
  assert np.isclose(z['relative_max_error'],claude[case]['errors'][kind],rtol=1e-12,atol=1e-20)
  p=np.load(D/(case+'-'+kind+'.npz'));actual=abs(p['worst_actual']-p['worst_reference']);assert np.isclose(max(actual)/z['reference_max'],z['relative_max_error'],rtol=1e-12)
  assert np.all(np.isfinite(p['reference_columns'])) and np.all(np.isfinite(p['actual_columns']))
 summary['matrix_checks'].append(r)
summary['timing_runs']=[load(f'setup-{e}-{i}.json') for e,i in [('native',0),('cached',0),('cached',1)]]
for r in summary['timing_runs']:
 base=pathlib.Path(r['out']).name
 for z in r['results']:
  y=np.load(D/(base+'-'+z['operator']+'.npy'));ref=np.load(D/(base+'-'+z['operator']+'-exact.npy'));err=float(max(abs(y[r['checked_rows']]-ref))/max(abs(ref)));assert np.isclose(err,z['relative_error'],rtol=1e-12)
a=summary['timing_runs'][0];bs=summary['timing_runs'][1:];summary['new_break_even']={}
for op in ['S','W']:
 native=np.mean(next(v for v in a['results'] if v['operator']==op)['product_seconds']);cached=np.mean([t for b in bs for v in b['results'] if v['operator']==op for t in v['product_seconds']]);setup=np.mean([b['setup_seconds'] for b in bs])-a['setup_seconds'];summary['new_break_even'][op]=dict(native_product_seconds=native,cached_product_seconds=cached,speedup=native/cached,products_to_amortize_setup=setup/(native-cached))
summary['regions']=load('REGION_PLANS.json');summary['thin_diagnostic']=load('THIN_DIAGNOSTIC.json');summary['accuracy_variants']=load('ACCURACY_DIAGNOSTIC.json')
for r in summary['accuracy_variants']:
 for kind,error in r['errors'].items():
  f=D/(r['case']+f"-d{r['digits']}-s{r['separation']}-"+kind+'.npz');p=np.load(f);got=float(np.max(abs(p['actual']-p['reference']))/np.max(abs(p['reference'])));assert np.isclose(got,error,rtol=1e-12)
for r in summary['thin_diagnostic']:
 values={k:complex(*v) for k,v in r['values'].items()};anchor=values['independent_GL_2048']
 for k,error in r['absolute_difference_from_GL2048'].items():assert np.isclose(abs(values[k]-anchor),error,rtol=1e-12,atol=1e-30)
summary['verified']=True
(D/'SUMMARY.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary['new_break_even'],indent=2));print('All retained comparisons verified')
