"""Combine saved numerical results; no solves or source edits."""
import json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def difference(first,second):
    with np.load(HERE/'benchmarks'/first/'fields.npz') as a, np.load(HERE/'benchmarks'/second/'fields.npz') as b:
        return {k:dict(angles=int(a[k].size),normalized_max=float(np.max(abs(a[k]-b[k]))/max(float(np.max(abs(a[k]))),1e-300))) for k in a.files}


if __name__=='__main__':
    rows={}
    for folder in sorted((HERE/'benchmarks').iterdir()):
        result=read(folder/'result.json');monitor=read(folder/'monitor.json');meta=read(folder/'metadata.json')
        factors=meta.get('compressed_factors',[])
        rows[folder.name]=dict(status=result['status'],seconds=result['solve_seconds'],
            peak_rss_gib=monitor['process_tree_peak_rss_bytes']/1024**3,
            peak_private_gib=monitor['process_tree_peak_private_bytes']/1024**3,
            quality_passed=result['quality_gate']['passed'],mesh_certified=result['mesh_convergence_certified'],
            total_factor_build_calls=result['runtime_profile']['stage_calls'].get('factorization'),
            actual_options=meta['execution_options'],
            final_unknowns=max((f['unknowns'] for f in factors),default=max((s.get('nodes',0) for s in meta.get('adaptive_mesh',{}).get('steps',[])),default=0)),
            final_inverse_builds=sum(f['factorizations'] for f in factors),
            final_hint_builds=sum(bool(f.get('preconditioner_hint',{}).get('accepted')) for f in factors),
            mesh_steps=[{k:s.get(k) for k in ('polynomial_degree','panels','nodes','backend','angle_batch_size')} for s in meta.get('adaptive_mesh',{}).get('steps',[])])
    base,on,leaf=(rows[n] for n in ('matched_hint_off','learned_hint','leaf64_experiment'))
    report=dict(runs=rows,hint_improvement_percent=100*(base['seconds']-on['seconds'])/base['seconds'],
        hint_peak_rss_saving_mib=1024*(base['peak_rss_gib']-on['peak_rss_gib']),
        leaf64_time_increase_percent=100*(leaf['seconds']-on['seconds'])/on['seconds'],
        leaf64_peak_rss_saving_mib=1024*(on['peak_rss_gib']-leaf['peak_rss_gib']),
        hint_fields=difference('matched_hint_off','learned_hint'),leaf_fields=difference('learned_hint','leaf64_experiment'),
        timing_scope='Single serial hint comparison; leaf experiment is another single run. 15 GHz runs establish capacity/accuracy, not comparative backend speed.')
    (HERE/'measurements.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='runs'},indent=2))
