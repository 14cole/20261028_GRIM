"""Summarize saved evidence without treating rejected/stopped runs as successes."""
import json
from pathlib import Path
import statistics
import re
import numpy as np

HERE=Path(__file__).resolve().parent


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def summarize():
    rows=[]
    for directory in sorted((HERE/'runs').iterdir()):
        if not (directory/'result.json').exists():continue
        result=read(directory/'result.json');case=read(directory/'case.json')
        monitor=read(directory/'monitor.json') if (directory/'monitor.json').exists() else {}
        row=dict(name=directory.name,case=case,status=result['status'],error=result.get('error'),
            seconds=result.get('solve_seconds'),peak_rss_gib=monitor.get('peak_rss_bytes',0)/1024**3,
            peak_private_gib=monitor.get('peak_private_bytes',0)/1024**3,
            stop_reason=monitor.get('stop_reason'))
        if (directory/'metadata.json').exists():
            data=read(directory/'metadata.json');steps=data.get('adaptive_mesh',{}).get('steps',[])
            row.update(actual_mode=data['execution_options']['factorization'],
                quality=data['quality_gate']['passed'],mesh_certified=data['mesh_convergence_certified'],
                final_unknowns=data.get('dense_largest_system'),
                steps=[{k:s.get(k) for k in ('panels','nodes','polynomial_degree','seconds','backend')} for s in steps])
            forecasts=[]
            for step in steps:
                choice=step.get('backend_selection') or {}
                predicted=(choice.get('candidates',{}).get(step['backend']) or {}).get('peak_gb')
                if predicted is not None:forecasts.append(predicted)
            row['max_selected_mesh_forecast_gib']=max(forecasts) if forecasts else None
            row['recorded_memory_estimates']=data.get('experimental_cpu',{}).get('memory_estimates',[])
            row['dense_hierarchical_factors']=data.get('hierarchical_factors',{})
            row['build_calls']=data.get('runtime_profile',{}).get('stage_calls',{}).get('factorization')
            row['final_factors']=[dict(unknowns=f['unknowns'],operator=f.get('compressed',{}).get('operator'),
                operator_bytes=f.get('compressed',{}).get('retained_bytes'),
                operator_rank=f.get('compressed',{}).get('max_rank'),
                inverse_bytes=(f.get('preconditioners') or [{}])[-1].get('bytes'),
                inverse_rank=(f.get('preconditioners') or [{}])[-1].get('max_rank'),
                backward_error=f.get('max_backward_error'),sampled_backward_error=f.get('max_sampled_backward_error'),
                hint=f.get('preconditioner_hint')) for f in data.get('compressed_factors',[])]
        if (directory/'stage_events.jsonl').exists():
            peaks={}
            for line in (directory/'stage_events.jsonl').read_text().splitlines():
                try:event=json.loads(line)
                except ValueError:continue
                key=event['stage_key'];value=event.get('process_tree_rss_bytes')
                if value is not None:peaks[key]=max(peaks.get(key,0),value/1024**3)
            row['sampled_stage_rss_gib']=peaks
        rows.append(row)
    comparisons={}
    for family in ('metal15','narrow15','hint'):
        matching=[r for r in rows if re.fullmatch(family+r'_r\d+_(dense|compressed|adaptive|on|off)',r['name']) and r['status']=='passed']
        if not matching:continue
        groups={}
        for row in matching:
            group=row['name'].rsplit('_',1)[-1]
            groups.setdefault(group,[]).append(row)
        summary={}
        reference=np.load(HERE/'runs'/matching[0]['name']/'fields.npz')
        for group,values in groups.items():
            differences=[]
            for row in values:
                with np.load(HERE/'runs'/row['name']/'fields.npz') as fields:
                    differences.append(max(float(np.max(abs(fields[pol]-reference[pol])))/
                        max(float(np.max(abs(reference[pol]))),1e-300) for pol in ('VV','HH')))
            seconds=[r['seconds'] for r in values]
            summary[group]=dict(count=len(values),seconds=seconds,median_seconds=statistics.median(seconds),
                min_seconds=min(seconds),max_seconds=max(seconds),max_field_difference=max(differences),
                peak_rss_gib=[r['peak_rss_gib'] for r in values],build_calls=[r.get('build_calls') for r in values])
        reference.close();comparisons[family]=summary
    probes=[]
    for reference_name,probe_name in [
        ('metal15_r0_dense','metal15_dense_budget_8gib'),
        ('metal15_r0_dense','metal15_auto_budget_6gib'),
        ('capacity_inlet_dielectric_15ghz','dielectric15_compressed_probe')]:
        reference_path=HERE/'runs'/reference_name/'fields.npz'
        probe_path=HERE/'runs'/probe_name/'fields.npz'
        if not reference_path.exists() or not probe_path.exists():continue
        with np.load(reference_path) as reference,np.load(probe_path) as fields:
            differences={pol:float(np.max(abs(fields[pol]-reference[pol])))/
                max(float(np.max(abs(reference[pol]))),1e-300) for pol in ('VV','HH')}
        probes.append(dict(reference=reference_name,probe=probe_name,
            normalized_field_differences=differences,scope='Single exploratory cross-check, not a repeated timing estimate.'))
    output=dict(runs=rows,comparisons=comparisons,exploratory_cross_checks=probes,
        notes=['Cold per-run timing history; serial runs with alternating mode order.',
               'Independent stage samples are approximate and not additive.',
               'Initial forecasts and final-mesh estimates must not be conflated.',
               'External guard stops and production rejections are not evidence of intrinsic impossibility.'])
    (HERE/'summary.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps(dict(runs=len(rows),statuses={s:sum(r['status']==s for r in rows) for s in set(r['status'] for r in rows)},
                         comparisons=comparisons),indent=2))


if __name__=='__main__':summarize()
