"""Recompute quoted array comparisons; summarize successes AND failed jobs."""
import pathlib,json,numpy as np
D=pathlib.Path(__file__).parent;out={'angles':[],'points':[],'galerkin':[],'systems':[],'nystrom':[],'failed_or_empty':[]};matched=[]
for f in sorted(D.glob('*.json')):
 name=f.stem
 if not name.startswith(('angle-','unmonitored-','point-','gal-','system-','nystrom-')) or name.endswith('-resources'):continue
 if not f.stat().st_size:out['failed_or_empty'].append({'name':name,'error':'empty output'});continue
 r=json.loads(f.read_text());resources=D/(name+'-resources.json');m=json.loads(resources.read_text()) if resources.exists() else None
 if r.get('error') or (m is not None and m['exit_code']!=0):out['failed_or_empty'].append({'name':name,'result':r,'exit_code':m.get('exit_code') if m else None});continue
 v={'name':name,**r};v['resources']={k:z for k,z in m.items() if k!='trace'} if m else None
 base=pathlib.Path(r['out']).name
 if name.startswith(('angle-','unmonitored-')):
  amp=np.load(D/(base+'-amplitude.npy'));rcs=np.load(D/(base+'-rcs.npy'));v['rcs_from_complex_max_absolute_difference']=float(np.max(abs(abs(amp)**2/(4*r['ka'])-rcs)));assert v['rcs_from_complex_max_absolute_difference']<1e-14
  residual=np.load(D/(base+'-residuals.npy'));assert abs(float(max(residual))-r['max_all_angle_fmm_relative_residual'])<1e-16
  out['angles'].append(v)
 elif name.startswith('point-'):
  value=np.load(D/(base+'.npy'));ref=np.load(D/(base+'-exact.npy'));error=float(np.max(abs(value[r['checked_rows']]-ref))/np.max(abs(ref)));assert np.isclose(error,r['point_relative_error'],rtol=1e-10,atol=1e-17);v['recomputed_point_error']=error
  if r.get('gradient_relative_error') is not None:
   value=np.load(D/(base+'-gradient.npy'));ref=np.load(D/(base+'-gradient-exact.npy'));error=float(np.max(abs(value[r['checked_rows']]-ref))/np.max(abs(ref)));assert np.isclose(error,r['gradient_relative_error'],rtol=1e-10,atol=1e-17)
  out['points'].append(v)
 elif name.startswith('gal-'):
  for z in r['results']:
   value=np.load(D/(base+'-'+z['operator']+'.npy'));ref=np.load(D/(base+'-'+z['operator']+'-exact.npy'));error=float(np.max(abs(value[r['checked_rows']]-ref))/np.max(abs(ref)));assert np.isclose(error,z['relative_error'],rtol=1e-10,atol=1e-17)
  out['galerkin'].append(v)
 elif name.startswith('system-'):
  ref=np.load(D/(base+'-reference.npy'))
  for z in r['results']:
   value=np.load(D/(base+'-'+z['preconditioner']+'.npy'));error=float(np.max(abs(value-ref))/np.max(abs(ref)));assert np.isclose(error,z['field_relative_max_error'],rtol=1e-10,atol=1e-17)
  out['systems'].append(v)
 else:
  ref=np.load(D/(base+'-reference-amplitude.npy'))
  for z in r['results']:
   value=np.load(D/(base+'-'+z['engine']+'-amplitude.npy'));error=float(np.max(abs(value-ref))/np.max(abs(ref)));assert np.isclose(error,z['complex_field_relative_error'],rtol=1e-10,atol=1e-17)
  out['nystrom'].append(v)
for group in [['angle-small-batch-0','angle-small-threads-0'],['angle-small-batch-1','angle-small-threads-1'],['angle-640-batch','angle-640-threads','angle-640-processes'],['angle-640-batch','unmonitored-640-processes'],*[['unmonitored-small-batch-'+str(i),'unmonitored-small-threads-'+str(i),'unmonitored-small-processes-'+str(i)] for i in range(2)]]:
 if not all((D/(n+'-amplitude.npy')).exists() for n in group):continue
 x=np.load(D/(group[0]+'-amplitude.npy'))
 for n in group[1:]:
  y=np.load(D/(n+'-amplitude.npy'));matched.append({'a':group[0],'b':n,'complex_field_relative_difference':float(np.max(abs(x-y))/np.max(abs(x))),'bitwise_equal':bool(np.array_equal(x,y))})
# Independent reproduction versus Claude's archived full-angle RCS.
f=D/'angle-1150-full-threads-rcs.npy';cf=D/'claude_reference/results/sig-star1150.npy'
if f.exists() and cf.exists():
 a,b=np.load(f),np.load(cf);out['claude_full_rcs_relative_difference']=float(np.max(abs(a-b))/np.max(abs(b))) if a.shape==b.shape else {'shape_a':a.shape,'shape_b':b.shape}
out['initial_systems']=[]
for f in sorted((D/'initial_low_frequency').glob('system-*.json')):
 if f.stem.endswith('-resources') or not f.stat().st_size:continue
 r=json.loads(f.read_text());base=pathlib.Path(r['out']).name;ref=np.load(f.parent/(base+'-reference.npy'))
 for z in r['results']:
  value=np.load(f.parent/(base+'-'+z['preconditioner']+'.npy'));err=float(np.max(abs(value-ref))/np.max(abs(ref)));assert np.isclose(err,z['field_relative_max_error'],rtol=1e-10,atol=1e-17)
 out['initial_systems'].append(r)
out['matched_complex_fields']=matched
(D/'SUMMARY.json').write_text(json.dumps(out,indent=2));print({k:len(v) if isinstance(v,list) else v for k,v in out.items()})
