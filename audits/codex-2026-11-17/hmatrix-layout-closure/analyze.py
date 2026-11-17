"""Replay reviewer arrays/timings and independent prior first-angle arrays."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;C=R/'claude'
read=lambda p:json.loads(p.read_text())
for m in ('source-provenance.json','binary-provenance.json'):
 for f in read(R/m)['files']:
  b=(C/f['path']).read_bytes()
  assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==f['sha']
summary=read(C/'accuracy.json');accuracy={};first_angles={}
stats=lambda a:[float(np.min(a)),float(np.median(a)),float(np.max(a))]
with np.load(R/'prior-first-angles.npz') as prior:
 for case in ('star-1024','slot-1024','star-4096'):
  with np.load(C/'out'/('old-'+case+'.npz')) as old,np.load(C/'out'/('new-'+case+'.npz')) as new:
   assert old.files==new.files
   assert old['rhs'].tobytes()==new['rhs'].tobytes() and old['exact'].tobytes()==new['exact'].tobytes()
   assert old['block'].tobytes()==new['block'].tobytes()
   norm=np.linalg.norm(old['exact'],axis=0)
   ea=np.linalg.norm(old['single']-old['exact'],axis=0)/norm
   eb=np.linalg.norm(new['single']-old['exact'],axis=0)/norm
   d=np.linalg.norm(old['single']-new['single'],axis=0)/norm
   batch=np.linalg.norm(old['single']-old['block'],axis=0)/norm
   values=dict(err_old=stats(ea),err_new=stats(eb),old_new_diff=stats(d),
      min_ratio_error_over_diff=float(np.min(np.minimum(ea,eb)/d)),
      max_abs_error_gap_over_diff=float(np.max(abs(ea-eb)/d)),
      new_closer_columns=int(np.sum(eb<ea)),old_closer_columns=int(np.sum(ea<eb)),
      block_vs_single_old=float(np.max(batch)),dense_residual=float(np.max(old['dense_residual'])))
   for k,v in values.items():assert np.allclose(v,summary[case][k],rtol=1e-12,atol=0),(case,k,v,summary[case][k])
   assert values['min_ratio_error_over_diff']>100
   accuracy[case]=dict(values,old_new_over_old_batch_max=float(np.max(d)/np.max(batch)))
   if case.endswith('1024'):
    name=case.split('-')[0]
    for variant,z in [('old',old),('new',new)]:assert prior[name+'_'+variant+'_single'].tobytes()==z['single'][:,0].tobytes()
    one=prior[name+'_old_single'];bn=prior[name+'_old_batch'];nn=prior[name+'_new_single']
    first_angles[name]=dict(independent_single_arrays_match_reviewer=True,
       old_batch_vs_single_relative_l2=float(np.linalg.norm(one-bn)/np.linalg.norm(one)),
       old_vs_new_single_relative_l2=float(np.linalg.norm(one-nn)/np.linalg.norm(one)))

timing=read(C/'timing.json');means={}
for variant in ('old','new','newF'):
 for repeat in ('a','b'):
  name=f't-{variant}-{repeat}';assert timing[name]==read(C/'out'/(name+'.timing.json'))['timing']
 means[variant]={op:float(np.mean([timing[f't-{variant}-{rep}'][op]['median'] for rep in ('a','b')])) for op in timing['t-old-a']}
ratios={variant:{op:means[variant][op]/means['old'][op] for op in means[variant]} for variant in ('new','newF')}
layout_ratio={op:means['newF'][op]/means['new'][op] for op in means['new']}
layout_pairs={op:[timing[f't-newF-{rep}'][op]['median']/timing[f't-new-{rep}'][op]['median'] for rep in ('a','b')] for op in means['new']}
assert all(abs(r-1)<.05 for v in ratios.values() for r in v.values())
assert layout_ratio['apply_1']>1.05 and layout_pairs['apply_1'][0]>1 and layout_pairs['apply_1'][1]<1
out=dict(all_pass=True,reviewer_array_files=6,reviewer_text_files=len(read(R/'source-provenance.json')['files']),
         accuracy=accuracy,prior_independent_first_angles=first_angles,timing_mean_process_medians_seconds=means,
         timing_ratios_to_old=ratios,timing_newF_over_new=layout_ratio,timing_newF_over_new_per_process=layout_pairs,
         new_solves=0,new_benchmarks=0,production_changes=0,
         scope='Full saved-array replay, timing-record arithmetic, cross-analysis with prior independent solves. No new numerical solve or timing claim.')
(R/'analysis.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
