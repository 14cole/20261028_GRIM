import pathlib,json,numpy as np
D=pathlib.Path(__file__).parent
points=[];systems=[];galerkin=[];errors=[]
for p in sorted(D.glob('fmm-points-*.json')):
 if p.stat().st_size:points.append(json.loads(p.read_text()))
for p in sorted(D.glob('fmm-galerkin-*.json')):
 if p.stat().st_size:
  r=json.loads(p.read_text());galerkin.append(r)
  if 'results' in r:
   name=p.name[:-5]
   for result in r['results']:
    a=np.load(D/(name+'-'+result['operator']+'.npy'))[r['checked_rows']];b=np.load(D/(name+'-'+result['operator']+'-sample.npy'))
    result['recomputed_sample_relative_max']=float(np.max(abs(a-b))/np.max(abs(b)))
for p in sorted(D.glob('fmm-system-*.json')):
 if not p.stat().st_size:errors.append(dict(file=p.name,error='empty JSON'));continue
 r=json.loads(p.read_text());name=p.name[:-5]
 if 'results' in r:
  reference=np.load(D/(name+'-reference.npy'))
  for result in r['results']:
   field=np.load(D/(name+'-'+result['preconditioner']+'.npy'));result['recomputed_field_error']=float(np.max(abs(field-reference))/np.max(abs(reference)))
   assert np.isfinite(field).all()
 systems.append(r)
(D/'FMM_ANALYSIS.json').write_text(json.dumps(dict(points=points,systems=systems,galerkin=galerkin,errors=errors),indent=2)+'\n')
print('points',len(points),'systems',len(systems),'galerkin',len(galerkin),'incomplete',errors)
for r in systems:
 print(r['kind'],r['n'],r['k'],r.get('error'),[(x['preconditioner'],x['iterations'],x['linear_checks_passed'],x['recomputed_field_error']) for x in r.get('results',[])])
for r in galerkin:print('galerkin',r['n'],r['ghz'],r.get('error'),r.get('results'))
