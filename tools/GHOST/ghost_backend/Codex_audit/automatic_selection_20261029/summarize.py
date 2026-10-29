"""Summarize matched transition trials, including failures and uncertified diagnostics."""
import json
from pathlib import Path
import statistics
import numpy as np

HERE=Path(__file__).resolve().parent
def read(path):return json.loads(path.read_text(encoding='utf-8'))
rows=[]
for case in read(HERE/'plan.json'):
    directory=HERE/'runs'/case['name']
    if not (directory/'monitor.json').exists():continue
    result=read(directory/'result.json');monitor=read(directory/'monitor.json')
    row=dict(name=case['name'],case=case,status=result['status'],seconds=result.get('solve_seconds'),
        error=result.get('error'),peak_rss_gib=monitor['peak_rss_bytes']/1024**3,
        peak_private_gib=monitor['peak_private_bytes']/1024**3)
    if (directory/'metadata.json').exists():
        metadata=read(directory/'metadata.json')
        row.update(quality_gate_passed=metadata['quality_gate']['passed'],
            mesh_certified=metadata['mesh_convergence_certified'],
            steps=[{k:s.get(k) for k in ('polynomial_degree','nodes','panels','seconds','backend','backend_selection')}
                   for s in metadata.get('adaptive_mesh',{}).get('steps',[])],
            final_compressed_factors=[{k:f.get(k) for k in ('unknowns','preconditioner_hint','preconditioners')}
                                      for f in metadata.get('compressed_factors',[])],
            dense_factors=metadata.get('hierarchical_factors'))
    if (directory/'stage_events.jsonl').exists():
        peaks={}
        for line in (directory/'stage_events.jsonl').read_text().splitlines():
            event=json.loads(line);value=event.get('process_tree_rss_bytes')
            if value is not None:peaks[event['stage_key']]=max(peaks.get(event['stage_key'],0),value/1024**3)
        row['inclusive_sampled_stage_peak_gib']=peaks
    rows.append(row)
comparisons={}
for family in ('dielectric15','narrow15'):
    reference_path=HERE/'runs'/f'{family}_r0_dense/fields.npz'
    if not reference_path.exists():continue
    groups={}
    with np.load(reference_path) as reference:
        for mode in ('dense','mixed','compressed'):
            matching=[r for r in rows if r['name'].startswith(family+'_') and r['name'].endswith('_'+mode)
                      and r['status']=='passed']
            if not matching:continue
            differences=[]
            for row in matching:
                with np.load(HERE/'runs'/row['name']/'fields.npz') as field:
                    differences.append(max(float(np.max(abs(field[pol]-reference[pol])))/
                        max(float(np.max(abs(reference[pol]))),1e-300) for pol in ('VV','HH')))
            groups[mode]=dict(count=len(matching),seconds=[r['seconds'] for r in matching],
                median_seconds=statistics.median(r['seconds'] for r in matching),
                peak_rss_gib=[r['peak_rss_gib'] for r in matching],max_normalized_field_difference=max(differences))
    comparisons[family]=groups
output=dict(completed_cases=len(rows),planned_cases=len(read(HERE/'plan.json')),runs=rows,comparisons=comparisons,
    notes=['Mixed is an audit-only prescribed transition among memory-admitted candidates.',
           'The condition diagnostic is uncertified; its relaxed gate is not a production change.',
           'Sampled inclusive stage peaks are not additive or isolated allocation measurements.'])
(HERE/'summary.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
print(json.dumps(dict(completed=len(rows),comparisons=comparisons),indent=2))
