"""Replay every numerical claim from raw records and saved field/residual arrays."""
import json,pathlib,os,numpy as np
root=pathlib.Path(__file__).resolve().parent;results=pathlib.Path(os.environ.get('RESULTS_DIR',root/'results'))
records={p.stem:json.loads(p.read_text()) for p in results.glob('*.json')}
comparisons={};maxback=0.;maxfield=0.
for name,record in records.items():
 assert not record['error'] and record['pending_bytes']==0,name
 with np.load(results/(name+'.npz')) as z:
  assert np.isfinite(z['field']).all()
  back=float(np.max(abs(z['residual'])/(z['row_norm'][:,None]*z['x_norm']+abs(z['rhs_rows']))))
  assert back<1e-12 and np.isclose(back,record['exact_backward_error'],rtol=1e-12,atol=0),name
  maxback=max(maxback,back)
 if name.startswith('final-'):
  baseline={'final-narrow':'dense-narrow-0-base','final-wide':'dense-wide-0-base','final-wide4t':'dense-wide4t-0-base'}[name]
 elif name.startswith('dense-'):
  baseline=name.rsplit('-',1)[0]+'-base'
 elif name.startswith('leaf-scale-'):baseline='leaf-scale-0-1'
 else:baseline=name.rsplit('-',1)[0]+'-1'
 with np.load(results/(baseline+'.npz')) as a,np.load(results/(name+'.npz')) as b:
  assert np.array_equal(a['angles'],b['angles'])
  err=float(np.max(abs(a['field']-b['field']))/np.max(abs(a['field'])))
  assert err<1e-8,(name,err);maxfield=max(maxfield,err)
  comparisons[name]=dict(reference=baseline,field_peak_relative=err,field_bit_identical=a['field'].tobytes()==b['field'].tobytes())
  if 'density' in a and 'density' in b:
   rel=float(np.linalg.norm(a['density']-b['density'])/np.linalg.norm(a['density']))
   assert rel<1e-7,(name,rel);comparisons[name]['density_relative_l2']=rel
dense={}
for geometry,dense_reference in [('star','dense-narrow-0-base'),('slot','dense-slot-0-base')]:
 if dense_reference not in records:continue
 for divisor in (1,2,4):
  name=f'leaf-{geometry}-{divisor}'
  with np.load(results/(dense_reference+'.npz')) as a,np.load(results/(name+'.npz')) as b:
   err=float(np.max(abs(a['field']-b['field']))/np.max(abs(a['field'])))
   assert err<1e-8,(name,'vs dense',err)
   comparisons[name]['field_vs_dense_peak_relative']=err
   if 'density' in a and 'density' in b:
    rel=float(np.linalg.norm(a['density']-b['density'])/np.linalg.norm(a['density']))
    assert rel<1e-7,(name,'density vs dense',rel)
    comparisons[name]['density_vs_dense_relative_l2']=rel
for fixture in ('narrow','wide','slot','narrow4t','wide4t'):
 repetitions=3 if fixture.endswith('4t') else 4
 names={variant:[f'dense-{fixture}-{rep}-{variant}' for rep in range(repetitions)] for variant in ('base','new')}
 if not all(name in records for group in names.values() for name in group):continue
 value={}
 for variant,group in names.items():
  items=[records[name] for name in group]
  value[variant]=dict(compute=[x['compute_seconds'] for x in items],solve=[x['stages']['solve'] for x in items],peak_gib=[x['compute_peak_gib'] for x in items])
 for metric in ('compute','solve','peak_gib'):
  a=np.array(value['base'][metric]);b=np.array(value['new'][metric])
  value[metric+'_change_percent']=float(100*(np.median(b)/np.median(a)-1))
  value[metric+'_paired_changes_percent']=(100*(b/a-1)).tolist()
 dense[fixture]=value
leaves={name:dict(operator_mib=x['array_bytes']/2**20,peak_gib=x['compute_peak_gib'],compute_seconds=x['compute_seconds'],stages=x['stages'],operator=x['operator'],refinement_steps=x['event']['refinement_steps']) for name,x in records.items() if name.startswith('leaf-')}
out=dict(passed=True,solves=len(records),max_exact_backward_error=maxback,max_field_peak_difference=maxfield,comparisons=comparisons,dense=dense,leaves=leaves)
pathlib.Path(os.environ.get('ANALYSIS_OUT',root/'analysis.json')).write_text(json.dumps(out,indent=2))
print(json.dumps(dict(passed=True,solves=len(records),max_backward_error=maxback,max_field_difference=maxfield,dense={k:{m:v for m,v in x.items() if m.endswith('change_percent')} for k,x in dense.items()}),indent=2))
