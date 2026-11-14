"""Verify pinned inputs, compare complete arrays, and summarize matched timings."""
import hashlib,json,os
from pathlib import Path
import numpy as np
root=Path('source');manifest=json.loads(Path('source_manifest.json').read_text())
for f in manifest['files']:
 data=(root/f['path']).read_bytes();assert len(data)==f['size'];assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==f['sha'],f['path']
new=root/'audits/claude-2026-11-14/fmm-scale-response-review/results';old=root/'audits/claude-2026-11-14/fmm-scale-validation-review/results'
prior=Path(os.environ['CODEX_PRIOR_RESULTS']) if os.environ.get('CODEX_PRIOR_RESULTS') else None
prior_manifest=Path('codex_evidence_manifest.json').read_bytes()
assert hashlib.sha1(b'blob '+str(len(prior_manifest)).encode()+b'\0'+prior_manifest).hexdigest()=='e1264b23d72e02c6e2f8d5f5d327a8dcc8059ea7'
prior_hashes={f['path']:f['sha256'] for f in json.loads(prior_manifest)['files']}
prior_verified=[]
pairs=[('cap_vs_combined',new/'cap-only-65536.npz',new/'combined-65536.npz'),('cap_vs_double_fmm',new/'cap-only-65536.npz',old/'fmm-65536.npz'),('mixed_vs_double_fmm',new/'mixed-65536.npz',old/'fmm-65536.npz'),('mixed_vs_combined',new/'mixed-65536.npz',new/'combined-65536.npz'),('adaptive_capped_vs_uncapped_32k',old/'adaptive-32768.npz',old/'adaptive-no-cap-32768.npz'),('production_repeat_32k',old/'compressed-32768-r2.npz',old/'compressed-32768.npz')]
if prior is not None:
 for label,a,name in [('combined_vs_prior_codex',new/'combined-65536.npz','adaptive-65536.npz'),('double_fmm_vs_prior_codex',old/'fmm-65536.npz','fmm-65536.npz'),('mixed_32k_vs_prior_codex',old/'storage-32768-te.npz','storage-32768-te.npz'),('adaptive_32k_vs_prior_codex',old/'adaptive-32768.npz','adaptive-32768.npz'),('production_32k_vs_prior_codex',old/'compressed-32768.npz','compressed-32768.npz')]:
  b=prior/name;assert hashlib.sha256(b.read_bytes()).hexdigest()==prior_hashes['results/'+name],name
  prior_verified.append(name);pairs.append((label,a,b))
comparisons={}
for label,a,b in pairs:
 with np.load(a) as aa,np.load(b) as bb:
  for key in ['rhs','angles','observation']:assert np.array_equal(aa[key],bb[key]),(label,key)
  item={}
  for key in ['density','field']:
   x,y=aa[key],bb[key];assert x.shape==y.shape and np.all(np.isfinite(x)) and np.all(np.isfinite(y))
   item[key+'_bitwise']=bool(x.dtype==y.dtype and x.tobytes(order='C')==y.tobytes(order='C'));item[key+'_relative_max']=float(np.max(abs(x-y))/np.max(abs(y)));item[key+'_relative_2']=float(np.linalg.norm(x-y)/np.linalg.norm(y))
  assert item['field_relative_max']<1e-10 and item['density_relative_2']<1e-8,(label,item)
  comparisons[label]=item
records={name:json.loads((new/(name+'.json')).read_text()) for name in ['cap-only-65536','combined-65536','mixed-65536']}
times={name:json.loads((new/(name+'.time')).read_text()) for name in records}
times['double-fmm-65536']=json.loads((old/'fmm-65536.time').read_text())
assert all(t['rc']==0 for t in times.values())
case=lambda r:(r['n'],r['k'],r.get('pol','TE'),tuple(r.get('eps',[3.,-.08])),r.get('star',True))
assert len({case(r) for r in records.values()})==1
cap,combined,mixed=[records[n] for n in ['cap-only-65536','combined-65536','mixed-65536']]
a,b=cap['adaptive_sketch_evidence'],combined['adaptive_sketch_evidence']
assert a['enabled'] is False and b['enabled'] is True and a['capped_calls']==b['capped_calls']==22
assert a['reduced_selections']==0 and b['reduced_selections']==161
assert cap['operator_evidence']['max_rank']>256 and combined['operator_evidence']['max_rank']>256
assert all(x['status']==0 for x in mixed['results'])
assert mixed['construction_operator_released'] and not mixed['production_certified']
with np.load(new/'mixed-65536.npz') as d:
 errors=np.max(abs(d['exact_row_residual'])/(d['exact_row_norm'][:,None]*np.max(abs(d['density']),axis=0)+abs(d['rhs'][d['rows']])),axis=0)
 assert np.allclose(errors,mixed['exact_sampled_rowwise_backward_error'],rtol=1e-12,atol=0)
ct,at,mt,dt=[times[n] for n in ['cap-only-65536','combined-65536','mixed-65536','double-fmm-65536']]
result=dict(commit=manifest['commit'],verified_input_files=len(manifest['files']),prior_codex_npz_verified=prior_verified,comparisons=comparisons,times=times,combined_vs_cap_wall_percent=100*(at['wall_s']/ct['wall_s']-1),mixed_vs_double_peak_reduction_percent=100*(1-mt['peak_gib']/dt['peak_gib']),mixed_vs_cap_peak_reduction_percent=100*(1-mt['peak_gib']/ct['peak_gib']),cap_wall_over_mixed_wall=ct['wall_s']/mt['wall_s'],mixed_vs_double_wall_percent=100*(mt['wall_s']/dt['wall_s']-1),assembly_fraction={n:records[n]['assembly_seconds']/times[n]['wall_s'] for n in ['cap-only-65536','combined-65536']},solve_seconds_two_angles={n:r['solve_seconds'] for n,r in records.items()},operator_ranks={n:records[n]['operator_evidence']['max_rank'] for n in ['cap-only-65536','combined-65536']},mixed_retained_bytes={k:mixed[k] for k in ['operator_bytes','inverse_bytes','preconditioner_reachable_array_bytes','fmm_bytes']},mixed_storage=mixed['preconditioner_storage_evidence'],mixed_saved_row_errors_recomputed=errors.tolist(),mixed_iterations=[r['iterations'] for r in mixed['results']],no_timing_equivalence_test=True)
Path('results/array-analysis.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
