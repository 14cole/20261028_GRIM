"""Summarize saved trial evidence without re-running or changing any solve."""
import json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def run(name):
    folder = HERE/'benchmarks'/name
    result, monitor, meta = (read(folder/file) for file in ('result.json','monitor.json','metadata.json'))
    factors = meta['compressed_factors']
    return dict(name=name, seconds=result['solve_seconds'], status=result['status'],
        peak_rss_gib=monitor['process_tree_peak_rss_bytes']/1024**3,
        peak_private_gib=monitor['process_tree_peak_private_bytes']/1024**3,
        quality_passed=result['quality_gate']['passed'],
        mesh_certified=result['mesh_convergence_certified'],
        final_unknowns=[f['unknowns'] for f in factors],
        gmres_columns=sum(f['gmres_columns'] for f in factors),
        upgrades=[f.get('preconditioner_upgrade') for f in factors],
        max_rhs_columns=max(f['max_rhs_columns'] for f in factors),
        execution_options=meta.get('execution_options'),
        preflight_angle_batch_size=result['preflight'].get('angle_batch_size'),
        resource_adjustment=result['preflight'].get('resource_adjustment'),
        max_sampled_backward_error=max(f.get('max_sampled_backward_error',0) for f in factors),
        max_operator_sampled_row_error=max(f['compressed'].get('sampled_row_error',0) for f in factors))


def differences(first, second):
    with np.load(HERE/'benchmarks'/first/'fields.npz') as a, np.load(HERE/'benchmarks'/second/'fields.npz') as b:
        return {key: dict(count=int(a[key].size),
            normalized_max_difference=float(np.max(abs(a[key]-b[key]))/max(float(np.max(abs(a[key]))),1e-300)))
            for key in a.files}


if __name__ == '__main__':
    names=['matched_upgrade_off','matched_upgrade_on','automatic_small_batch']
    rows=[run(name) for name in names]
    before, after, constrained=rows
    result=dict(runs=rows,
        timing_scope='One serial matched pair, four threads, no validation suite running. Early overlapping diagnostic runs excluded.',
        speedup_percent=100*(before['seconds']-after['seconds'])/before['seconds'],
        extra_peak_rss_mib=(after['peak_rss_gib']-before['peak_rss_gib'])*1024,
        constrained_peak_rss_reduction_mib=(after['peak_rss_gib']-constrained['peak_rss_gib'])*1024,
        upgraded_field_difference=differences(names[0],names[1]),
        constrained_field_difference=differences(names[1],names[2]))
    (HERE/'measurements.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
