"""Check pinned review inputs and recompute descriptive timing comparisons.
No statistical significance or zero-effect claim is inferred from two repeats.
"""
import hashlib,json,statistics
from pathlib import Path
j=json.loads(Path('review_inputs.json').read_text());files={}
for group in ['review_files','codex_files']:
 for f in j[group]:
  data=f['content'].encode();actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
  assert actual==f['sha'],f['path']
  files[(group,f['path'])]=f['content']
def read(group,path):return json.loads(files[group,path])
def claude(name):return read('review_files','results/'+name+'.time')
def codex(name):return read('codex_files','results/'+name+'.time.json')
production=[claude(n)['wall_s'] for n in ['compressed-32768','compressed-32768-r2']]
adaptive=[claude(n)['wall_s'] for n in ['adaptive-32768','adaptive-no-cap-32768']]
assert all(claude(n)['rc']==0 for n in ['compressed-32768','compressed-32768-r2','adaptive-32768','adaptive-no-cap-32768','fmm-65536','storage-32768-te'])
ca=read('review_files','results/adaptive-32768.json')['adaptive_sketch_evidence'];ua=read('review_files','results/adaptive-no-cap-32768.json')['adaptive_sketch_evidence'];oa=read('codex_files','results/adaptive-32768.json')['adaptive_sketch_evidence']
assert ca==oa
assert ca['capped_calls']==ua['capped_calls']==0
assert {k:v for k,v in ca.items() if k!='initial_rank_cap'}=={k:v for k,v in ua.items() if k!='initial_rank_cap'}
def summary(values):return dict(values_seconds=values,minimum_seconds=min(values),maximum_seconds=max(values),mean_seconds=statistics.mean(values),count=len(values))
oom=claude('adaptive-no-cap-65536');assert oom['rc']==-9 and not oom['stopped_by_guard']
fmm=claude('fmm-65536');ours=codex('fmm-65536')
result=dict(review_commit=j['review_commit'],codex_commit=j['codex_commit'],verified_input_blobs=len(files),production_32768=summary(production),adaptive_32768=summary(adaptive),adaptive_mean_change_percent=100*(statistics.mean(adaptive)/statistics.mean(production)-1),descriptive_pairs_change_percent=[100*(a/p-1) for a,p in zip(adaptive,production)],cap_never_used_at_32768=True,adaptive_statistics_match_prior_codex=True,no_significance_test_performed=True,speedup_claim_withdrawn=True,fmm_65536=dict(claude_wall_seconds=fmm['wall_s'],codex_wall_seconds=ours['wall_seconds'],claude_peak_gib=fmm['peak_gib'],codex_peak_gib=ours['peak_gib']),uncapped_65536=dict(termination='cgroup OOM; no accepted solution',**oom),array_comparisons='Claude cross_checks.txt reports comparisons; Claude full solution arrays are not in the reviewed folder tree and were not independently recomputed in this response.')
Path('analysis.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
