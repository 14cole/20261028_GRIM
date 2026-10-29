"""Summarize completed studies and regression results without rerunning solves."""
from pathlib import Path
import json,hashlib,statistics
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];GIB=1024**3
read=lambda p:json.loads(p.read_text())
rows=[]
for case in read(HERE/'plan.json'):
    directory=HERE/'runs'/case['name'];result=read(directory/'result.json');monitor=read(directory/'monitor.json')
    row=dict(name=case['name'],geometry=case['geometry'],profile=case['profile'],status=result['status'],
        seconds=result.get('solve_seconds',result.get('elapsed_seconds')),certified=result.get('certified',False),
        peak_tree_rss_gib=monitor['peak_tree_rss']/GIB,peak_tree_private_gib=monitor['peak_tree_private']/GIB,
        error=result.get('error'),phase=result.get('phase'),stop_reason=monitor['stop_reason'],
        reference_relative_field_errors=result.get('reference_relative_field_errors'))
    row['outcome_class'] = ('certified' if result.get('certified') else
        'geometry_panel_limit' if 'panel limit' in result.get('error','') else
        'memory_admission' if result.get('error_type')=='MemoryError' else
        'external_trial_guard' if monitor['stop_reason'] else 'other_failure')
    metadata=directory/'metadata.json'
    if metadata.exists():
        m=read(metadata);row.update(linear_node_count=m.get('linear_node_count'),mesh_certified=m.get('mesh_convergence_certified'),quality_passed=m.get('quality_gate',{}).get('passed'))
    rows.append(row)
controls=[r for r in rows if r['name'].startswith('inlet_')]
assert all(r['status']=='passed' and r['certified'] for r in controls)
four=statistics.mean(r['seconds'] for r in controls if r['profile']=='four')
auto=statistics.mean(r['seconds'] for r in controls if r['profile']=='auto')
validation=read(HERE/'validation_results.json');assert all(r['outcome']=='passed' for r in validation)
summary=dict(runs=rows,throughput=dict(four_mean_seconds=four,automatic_mean_seconds=auto,
    saved_seconds=four-auto,saved_percent=100*(four-auto)/four,
    scope='Existing automatic profile versus four assembly/four BLAS; not a code revision comparison.'),
    validation=dict(unique_tests=len({r['test'] for r in validation}),reports=len(validation),
        files=sorted({r['test'].split('::')[0] for r in validation})),
    source_matches={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected for name,expected in read(HERE/'tested_source_hashes.json').items()})
assert all(summary['source_matches'].values())
(HERE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
