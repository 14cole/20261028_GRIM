"""Check archived numerical claims; does not rerun any expensive solver."""
import json,pathlib,numpy as np
D=pathlib.Path(__file__).parent
m=json.loads((D/'METHODS_ANALYSIS.json').read_text());f=json.loads((D/'FMM_ANALYSIS.json').read_text());counts={}
assert len(m['solves'])==42
for r in m['solves']:
 assert r['error'] is None and r['quality_passed'] is True,r['name']
 a=np.load(D/(r['name']+'.npy'));assert np.isfinite(a).all()
 raw=json.loads((D/(r['name']+'.json')).read_text())
 # Source identities are checked explicitly below, without relying on runtime policy labels.
 assert raw['source_sha256']=='817d4cc7fee52b3b5b34d10380e4277d6bcb91bb4f0a2effc458fbf7947a3216'
counts['complete_solver_runs']=len(m['solves'])
for r in m['comparisons']:assert r['relative_max']<1e-8,r
counts['solver_field_comparisons']=len(m['comparisons'])
probes=[]
for p in D.glob('holdout-adjoint-*.json'):
 probes.extend(json.loads(p.read_text())['research']['probes'])
assert len(probes)==18
for r in probes:assert r['backward']<=1e-12 and r['forward_dimensionless']<1e-8
counts['random_rhs_inverse_modes']=len(probes)
ops=json.loads((D/'FMM_OPERATOR_CHECKS.json').read_text());assert len(ops)==12
assert max(r['error'] for r in ops)<1e-10;counts['galerkin_operator_checks']=len(ops)
assert len(f['points'])==9 and len(f['systems'])==9 and len(f['galerkin'])==4 and not f['errors']
for r in f['points']:
 assert r['error'] is None and r['sampled_relative_max']<1e-10
 name=f"fmm-points-{r['n']}-{r['ghz']}-{r['rhs']}";a=np.load(D/(name+'.npy'));assert a.shape==(r['rhs'],r['n']) and np.isfinite(a).all()
counts['point_kernel_cases']=len(f['points']);counts['fmm_preconditioned_system_cases']=0;counts['fmm_rhs_solutions']=0
for r in f['systems']:
 for q in r['results']:
  assert q['linear_checks_passed'] and max(q['physical_backward_error'],q['scaled_backward_error'])<=1e-12
  assert q['recomputed_field_error']<1e-9
  counts['fmm_preconditioned_system_cases']+=1;counts['fmm_rhs_solutions']+=len(q['iterations'])
for kind in ['PEC','TE','TM']:
 rows=[r for r in f['systems'] if r['kind']==kind and not r['star']];rows.sort(key=lambda r:r['n']);key='analytic_backscatter_relative_error' if kind=='PEC' else 'analytic_sigma_relative_error'
 for i in range(2):assert rows[1]['results'][i][key] < .3*rows[0]['results'][i][key]
counts['analytic_mesh_refinement_comparisons']=6
for r in f['galerkin']:
 assert not r.get('error') and len(r['results'])==2
 for q in r['results']:assert q['recomputed_sample_relative_max']<1e-10
counts['large_galerkin_products']=8
assert json.loads((D/'PRODUCTION_UNCHANGED.json').read_text())['all_match']
(D/'VERIFICATION.json').write_text(json.dumps(dict(passed=True,counts=counts),indent=2)+'\n');print(counts)
