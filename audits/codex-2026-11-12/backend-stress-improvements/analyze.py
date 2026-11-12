"""Aggregate all outcomes, complete-field differences and analytic circle checks."""
import json,sys,math,warnings,re
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent
sys.path.insert(0,str(Path(sys.argv[1])/'tools/GHOST'))
from ghost_backend.validation.cylinder import (sigma_pec_cylinder,sigma_dielectric_cylinder,
    sigma_coated_pec_cylinder,pec_cylinder_backscatter_amplitude)

def values(x,key):
    if isinstance(x,dict):
        if key in x:yield x[key]
        for value in x.values():yield from values(value,key)
    elif isinstance(x,list):
        for value in x:yield from values(value,key)

def analyze():
    rows=[];by_id={};pairs=[];analytic=[]
    for f in sorted((P/'results').glob('*.json')):
        if f.name.endswith(('.monitor.json','.metadata.json','.samples.json')):continue
        d=json.loads(f.read_text());spec=d['spec'];name=spec['case']
        if not f.with_name(name+'.monitor.json').exists():continue
        monitor=json.loads(f.with_name(name+'.monitor.json').read_text())
        metadata=f.with_name(name+'.metadata.json')
        meta=json.loads(metadata.read_text()) if metadata.exists() else {}
        resources=d.get('resources',[])
        # A watchdog can interrupt before the final summary; retain resource events.
        if not resources:
            events=f.with_name(name+'.events.jsonl')
            if events.exists():
                for line in events.read_text().splitlines():
                    try:event=json.loads(line)
                    except ValueError:continue
                    if event.get('event')=='resources':resources.append(event['resources'])
        plans=[r.get('memory_estimate') for r in resources if r.get('memory_estimate')]
        plans+=list(values(meta.get('memory_accounting',{}),'plan'))
        plans+=meta.get('experimental_cpu',{}).get('memory_estimates',[])
        profiles=meta.get('runtime_profile',{})
        factors=meta.get('compressed_factors',[])
        condition=meta.get('condition_est_max')
        if condition is None and d['error']:
            match=re.search(r'condition_est_max=([0-9.eE+-]+)',d['error'])
            if match:condition=float(match.group(1))
        row=dict(case=name,geometry_id=spec['geometry_id'],group=spec.get('group'),backend=spec['backend'],
            error=d['error'],status='success' if d['error'] is None else
            'timeout' if 'watchdog_wall' in d['error'] else 'memory_rejection' if 'MemoryError' in d['error'] else
            'watchdog_memory' if 'watchdog_process_tree' in d['error'] else 'solver_rejection',
            wall_seconds=d['wall_seconds'],peak_parent_rss_gib=max(d.get('rss_highwater_gib',0),monitor['peak_parent_rss_gib'],profiles.get('sampled_peak_process_rss_bytes',0)/2**30),
            peak_tree_rss_gib=max(monitor['peak_tree_rss_gib'],profiles.get('sampled_peak_process_tree_rss_bytes',0)/2**30),
            children=monitor['max_children'],actual_unknowns=max([r['system_dofs'] for r in resources]or[0]),
            actual_panels=max([r['panels'] for r in resources]or[0]),
            matrix_floor_gib=16*max([r['system_dofs'] for r in resources]or[0])**2/2**30,
            quality_passed=d.get('quality_gate',{}).get('passed'),
            mesh_certified=meta.get('mesh_convergence_certified',False),
            condition_est_max=condition,residual_norm_max=meta.get('residual_norm_max'),
            stages=profiles.get('stage_seconds',{}),geometry=d.get('geometry'),
            forecast_gib=max([v['peak_bytes']/2**30 for v in plans if isinstance(v,dict) and 'peak_bytes'in v]or[0]),
            inverse_ranks=[v for f in factors for pre in f.get('preconditioners',[]) for v in values(pre,'max_rank')],
            operator_ranks=[f['compressed']['max_rank'] for f in factors if 'max_rank' in f.get('compressed',{})],
            effective_backend=meta.get('linear_backend'),factor_evidence=factors,
            spec=spec)
        rows.append(row);by_id.setdefault(spec['geometry_id'],{})[spec['backend']]=row
        if d['error'] is not None:continue
        assert row['quality_passed'],name
        field=np.load(f.with_name(name+'.npz'))['field'];assert np.isfinite(field).all(),name
        if spec.get('shape','circle')!='circle' or spec['material']=='multilayer' or spec.get('magnetic_thin_layer'):continue
        samples=json.loads(f.with_name(name+'.samples.json').read_text());radius=spec['length_m']/2
        refs={};eps=complex(*spec.get('eps',[4.,-.2]));freq=spec['frequency_ghz']*1e9
        for pol in ('TE','TM'):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore')
                    ref=(sigma_pec_cylinder(radius,freq,pol) if spec['material']=='pec' else
                        sigma_dielectric_cylinder(radius,eps,1,freq,pol) if spec['material']=='diel' else
                        sigma_coated_pec_cylinder(radius*spec.get('inner_ratio',.7),radius,eps,1,freq,pol))
                measured=np.array([s['rcs_linear'] for s in samples if s['polarization_internal']==pol])
                entry=dict(reference_width=ref,valid=bool(np.isfinite(ref) and ref>0))
                if entry['valid']:
                    entry.update(max_relative_width_error=float(np.max(abs(measured-ref))/ref),
                        max_db_error=float(np.max(abs(10*np.log10(measured/ref)))))
                    if spec['material']=='pec':
                        amp=pec_cylinder_backscatter_amplitude(radius,freq,pol)
                        ff=np.array([complex(s['rcs_amp_real'],s['rcs_amp_imag']) for s in samples if s['polarization_internal']==pol])
                        entry['max_relative_complex_error']=float(np.max(abs(ff-amp))/abs(amp))
                refs[pol]=entry
            except Exception as exc:refs[pol]=dict(valid=False,error=str(exc))
        analytic.append(dict(case=name,polarizations=refs))
    indexed={r['case']:r for r in rows}
    angle_names={method:'experiment-pec8000-181angles-'+method for method in ('dense','compressed')}
    if all(name in indexed for name in angle_names.values()):
        angle_pair={method:indexed[name] for method,name in angle_names.items()}
        assert angle_pair['dense']['geometry']['sha256']==angle_pair['compressed']['geometry']['sha256']
        by_id['experiment-pec8000-181angles']=angle_pair
    for gid,methods in by_id.items():
        if not all(k in methods for k in ('dense','compressed')):continue
        a,b=methods['dense'],methods['compressed'];pair=dict(geometry_id=gid,dense_status=a['status'],compressed_status=b['status'])
        if a['status']==b['status']=='success':
            x=np.load(P/'results'/(a['case']+'.npz'))['field'];y=np.load(P/'results'/(b['case']+'.npz'))['field']
            if x.shape==y.shape:
                def keys(name):
                    return [(r['frequency_ghz'],r['theta_inc_deg'],r['polarization_internal']) for r in json.loads((P/'results'/(name+'.samples.json')).read_text())]
                assert keys(a['case'])==keys(b['case']),gid
                pair.update(fields=len(x),relative_max_field_difference=float(max(abs(x-y))/max(abs(x))),
                    bitwise_equal=bool(np.array_equal(x,y)),compressed_over_dense_time=b['wall_seconds']/a['wall_seconds'],
                    compressed_over_dense_tree_rss=b['peak_tree_rss_gib']/a['peak_tree_rss_gib'],
                    mesh_unknowns_match=a['actual_unknowns']==b['actual_unknowns'])
        pairs.append(pair)
    experiments=[]
    for row in rows:
        ref=row['spec'].get('reference_case')
        if not ref or ref not in indexed:continue
        baseline=indexed[ref];record=dict(case=row['case'],reference=ref,status=row['status'],reference_status=baseline['status'])
        if row['status']==baseline['status']=='success':
            def fieldmap(name):
                data=json.loads((P/'results'/(name+'.samples.json')).read_text())
                return {(r['frequency_ghz'],r['theta_inc_deg'],r['polarization_internal']):complex(r['rcs_amp_real'],r['rcs_amp_imag']) for r in data}
            a,b=fieldmap(ref),fieldmap(row['case']);common=sorted(set(a)&set(b));assert common
            x=np.array([a[k] for k in common]);y=np.array([b[k] for k in common])
            record.update(compared_fields=len(common),all_reference_fields=len(common)==len(a),
                relative_max_field_difference=float(max(abs(x-y))/max(abs(x))),
                bitwise_equal=bool(np.array_equal(x,y)),time_ratio=row['wall_seconds']/baseline['wall_seconds'],
                tree_rss_ratio=row['peak_tree_rss_gib']/baseline['peak_tree_rss_gib'])
        experiments.append(record)
    summary=dict(cases=len(rows),counts={status:sum(r['status']==status for r in rows) for status in sorted(set(r['status']for r in rows))},
        rows=rows,pairs=pairs,analytic=analytic,experiments=experiments)
    (P/'SUMMARY.json').write_text(json.dumps(summary,indent=2,default=str)+'\n')
    print(json.dumps(dict(cases=len(rows),counts=summary['counts'],worst_field_pairs=sorted([p for p in pairs if 'relative_max_field_difference'in p],key=lambda p:p['relative_max_field_difference'],reverse=True)[:8]),indent=2))

if __name__=='__main__':analyze()
