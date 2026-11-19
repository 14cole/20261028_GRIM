"""Cross-analysis of immutable reviewer records; no numerical solve."""
import pathlib,json,numpy as np
r=pathlib.Path(__file__).resolve().parent;c=r/'claude';records={p.stem:json.loads(p.read_text()) for p in (c/'results').glob('*.json') if not p.name.endswith('.time.json')}
times=[json.loads(p.read_text()) for p in (c/'results').glob('*.time.json')];assert all(x['returncode']==0 for x in times)
def signature(s):return tuple(json.dumps(s.get(k,180 if k=='count' else None),sort_keys=True) for k in ('material','shape','length_m','frequency_ghz','eps','inner_eps','pol','count','ppw'))
anchors={}
for name,d in records.items():
 if name.startswith('main-') and d['spec']['method']=='dense' and (c/'results'/(name+'-fields.npz')).exists():
  key=signature(d['spec'])
  if key not in anchors or d['spec'].get('batch',256)==256:anchors[key]=name
fields={};unmatched=[]
for p in (c/'results').glob('*-fields.npz'):
 name=p.name[:-11];d=records[name];assert not d.get('error'),name
 with np.load(p) as z:x=z['field'];assert np.isfinite(x).all()
 key=signature(d['spec'])
 if key not in anchors:unmatched.append(name);continue
 reference=anchors[key]
 with np.load(c/'results'/(reference+'-fields.npz')) as z:y=z['field']
 assert x.shape==y.shape
 error=float(np.max(abs(x-y))/np.max(abs(y)));assert error<1e-7,(name,error)
 fields[name]=dict(reference=reference,peak_relative_error=error,bit_identical=np.array_equal(x,y))
timing={}
for variant in ('main','patched'):
 ds=[d for name,d in records.items() if name.startswith('u-'+variant+'-partial-b16-t4-')]
 assert len(ds)==4
 timing[variant]=dict(wall=[d['wall_seconds'] for d in ds],solve=[sum(x['solve_seconds'] for x in d['hooks']['dense_gate']) for d in ds])
timing['solve_change_percent']=float(100*(np.median(timing['patched']['solve'])/np.median(timing['main']['solve'])-1))
timing['wall_change_percent']=float(100*(np.median(timing['patched']['wall'])/np.median(timing['main']['wall'])-1))
leaves={}
for name,d in records.items():
 if d['spec']['method']=='compressed' and 'leaf_divisor' in d['spec']:
  factor=d['factors'][0];operator=factor['compressed']
  leaves[name]=dict(leaf_divisor=d['spec']['leaf_divisor'],operator_bytes=operator['retained_bytes'],inverse_bytes=factor['preconditioners'][-1]['bytes'],peak_gib=d['peak_gib'],wall_seconds=d['wall_seconds'])
out=dict(review='df18342afb09cd6c6cd3b954c5ef1d8afb3b3894',successful_process_records=len(times),field_comparisons=fields,unmatched_fields=unmatched,timing=timing,leaves=leaves,density_limitation='Reviewer publishes first-batch hashes but not the corresponding solution arrays; density-error values cannot be independently recomputed from those hashes.')
with np.load(c/'results/s-coated-TE-leafdiv1-fields.npz') as a,np.load(c/'results/s-coated-TE-leafdiv2-fields.npz') as b:
 error=float(np.max(abs(a['field']-b['field']))/np.max(abs(a['field'])))
 assert error<1e-7
 out['coated_leaf_field_difference']=dict(peak_relative=error,dense_anchor_available=False)
(r/'claude-replay.json').write_text(json.dumps(out,indent=2));print(json.dumps(dict(process_records=len(times),compared_fields=len(fields),unmatched=len(unmatched),timing=timing),indent=2))
