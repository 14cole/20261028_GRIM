"""Assert accuracy and summarize measurements without rerunning solves."""
import pathlib,json,os,numpy as np
r=pathlib.Path(__file__).resolve().parent;fresh=pathlib.Path(os.environ.get('FRESH_DIR',r/'fresh'))
out={};physical={p.stem:json.loads(p.read_text()) for p in fresh.glob('partial-*.json')}
sources=json.loads((r/'source-provenance.json').read_text())['sources']
assert len(physical)==20
for name,d in physical.items():
 assert d['error'] is None and d['metadata']['quality_gate']['passed'],name
 assert d['source_blob']==sources[name.rsplit('-',1)[1]]['git_blob'],name
 assert all(x['num_threads']==d['spec']['threads'] for c in d['calls'] for x in c['pools'])
 ref=name.rsplit('-',1)[0]+'-main'
 with np.load(fresh/(name+'.npz')) as z,np.load(fresh/(ref+'.npz')) as a:
  assert a['density'].shape[0]==z['density'].shape[0]==4146
  assert np.array_equal(z['rhs'],a['rhs'])
  field=float(np.max(abs(z['field']-a['field']))/np.max(abs(a['field'])))
  density=float(np.max(abs(z['density']-a['density']))/np.max(abs(a['density'])))
  assert field<1e-8 and density<1e-7,(name,field,density)
  d['comparison']=dict(reference=ref,field_peak_relative=field,first_up_to_16_density_peak_relative=density,field_bits_equal=np.array_equal(z['field'],a['field']))
summary={}
for t in (1,4):
 values={variant:[physical[f'partial-t{t}-r{rep}-{variant}']['solve_seconds'] for rep in range(2)] for variant in ('main','old','direct')}
 summary[str(t)]=dict(values=values,median={v:float(np.median(s)) for v,s in values.items()},old_change_percent=float(100*(np.median(values['old'])/np.median(values['main'])-1)),direct_change_percent=float(100*(np.median(values['direct'])/np.median(values['main'])-1)))
extra={v:[physical[f'partial-t4-r{rep}-{v}']['solve_seconds'] for rep in range(4)] for v in ('main','direct')}
summary['4_direct_confirmatory']=dict(values=extra,median={v:float(np.median(x)) for v,x in extra.items()},direct_change_percent=float(100*(np.median(extra['direct'])/np.median(extra['main'])-1)),paired_change_percent=[100*(b/a-1) for a,b in zip(extra['main'],extra['direct'])])
out['physical']=dict(cases={k:{s:v[s] for s in ('solve_seconds','wall_seconds','peak_gib','source_blob','comparison')} for k,v in physical.items()},summary=summary)
bench={}
for p in fresh.glob('*pools-*.json'):
 d=json.loads(p.read_text());by={v:[x['wall_seconds'] for x in d['records'] if x['variant']==v] for v in ('baseline','numpy_f','direct')}
 bench[p.stem]=dict(spec=d['spec'],pools=d['pools'],times=by,median={v:float(np.median(x)) for v,x in by.items()})
out['benchmarks']=bench
synthetic={};maxerr=0.;identical=0
with np.load(fresh/'synthetic-main.npz') as a,np.load(fresh/'synthetic-direct.npz') as b:
 assert a.files==b.files and len(a.files)==820
 for key in a.files:
  x,y=a[key],b[key];assert np.isfinite(x).all() and np.isfinite(y).all()
  error=float(np.max(abs(x-y))/max(float(np.max(abs(x))),1e-300));assert error<1e-7,(key,error)
  same=np.array_equal(x,y);maxerr=max(maxerr,error);identical+=int(same)
  synthetic[key]=dict(peak_relative=error,bit_identical=same)
for variant in ('main','direct'):
 d=json.loads((fresh/f'synthetic-{variant}.json').read_text());assert len(d['records'])==820 and all(x.get('ok') for x in d['records'])
out['synthetic']=dict(cases=820,bit_identical=identical,max_peak_relative=maxerr,comparisons=synthetic)
out['all_pass']=True
pathlib.Path(os.environ.get('ANALYSIS_OUT',r/'analysis.json')).write_text(json.dumps(out,indent=2))
print(json.dumps(dict(physical=summary,synthetic=out['synthetic']|{'comparisons':'see analysis.json'},all_pass=True),indent=2))
