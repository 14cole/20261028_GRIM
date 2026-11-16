"""Pinned-record audit and fresh-run checks; does not claim new far-field solves."""
from pathlib import Path
import os,json,hashlib
import numpy as np
R=Path(__file__).resolve().parent;D=Path(os.environ.get('RESULTS_DIR',str(R/'results')))
sha=lambda a:hashlib.sha256(a.tobytes(order='C')).hexdigest()
provenance=json.loads((R/'source-provenance.json').read_text())
for f in provenance['files']:
    b=(R/'claude'/f['path']).read_bytes()
    assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==f['sha']
controls=R/'claude/ecc046c_controls';manifest=json.loads((controls/'control_array_hashes.json').read_text())
control_checks=[]
for p in sorted(controls.glob('*.npz')):
    label=p.stem.removesuffix('-control')
    with np.load(p) as z:
        for k,v in manifest[label].items():
            assert list(z[k].shape)==v['shape'] and sha(z[k])==v['sha256_c_order']
        den=z['row_norm'][:,None]*np.max(abs(z['density']),axis=0)+abs(z['rhs'][z['rows']])
        back=float(np.max(abs(z['residual'])/den));assert back<1e-12
        control_checks.append(dict(label=label,arrays=len(z.files),max_backward_error=back))
groups={}
for prefix in ['star8192','slot2048']:
    rows={k:v for k,v in manifest.items() if k.startswith(prefix)}
    unique={k:len({v[k]['sha256_c_order'] for v in rows.values()}) for k in next(iter(rows.values()))}
    assert unique['density']==1
    assert unique['residual']==(2 if prefix=='star8192' else 1)
    groups[prefix]=dict(runs=len(rows),unique_hash_counts=unique)
published=[]
for variant in ['orig','fixed']:
    for p in sorted((R/'claude'/variant).glob('*.json')):
        a=json.loads(p.read_text());s=[x for x in a['sequence'] if 'corrections' in x]
        assert a['max_backward_error']<1e-12 and a['new_stable_bitwise_equal_stable']
        c=a['cancel'];assert c['raised']=='Cancel' and c['inverse_is_none'] and c['old_inverse_collected']
        assert c['flag_before']==c['flag_after_cancel']
        if variant=='fixed':assert not c['flag_after_successful_rebuild'] and a['rebuilt_stable_bitwise_equal_stable'] and c['recovered_stable_bitwise_equal_stable']
        adv=a['adversarial'];assert adv['bitwise_all_equal'] and adv['total_factorizations']==3
        expected=(3 if variant=='fixed' else 1) if a['upgrades_naturally'] else 0
        assert adv['real_attempts']==expected
        published.append(dict(variant=variant,case=p.stem,unknowns=2*a['spec']['n'],corrections=[x['corrections'] for x in s],real_attempts=adv['real_attempts'],max_backward_error=a['max_backward_error']))
fresh={};arrays={}
for variant,pinned in [('original','orig'),('fixed','fixed')]:
    a=json.loads((D/(variant+'.json')).read_text());b=json.loads((R/'claude'/pinned/'slot-512.json').read_text())
    assert json.loads((D/(variant+'.time.json')).read_text())['returncode']==0
    # Compare all measurements, allowing only local source/output paths to differ.
    for key in a:
        if key not in ('spec','source'):assert a[key]==b[key],(variant,key)
    with np.load(D/(variant+'-first-two.npz')) as z:arrays[variant]={k:z[k] for k in z.files}
    fresh[variant]=dict(corrections=[s['corrections'] for s in a['sequence'] if 'corrections' in s],
        denied_corrections=[s['corrections'] for s in a['adversarial']['steps']],real_attempts=a['adversarial']['real_attempts'],
        record_measurements_identical_to_claude=True,max_backward_error=a['max_backward_error'],
        hashes={k:sha(v) for k,v in arrays[variant].items()})
for k in arrays['original']:assert arrays['original'][k].tobytes()==arrays['fixed'][k].tobytes()
out=dict(source_blobs_verified=len(provenance['files']),control_arrays=control_checks,manifest_groups=groups,published_records=published,
         fresh=fresh,fresh_processes=2,fresh_density_solves=32,first_and_stable_bit_identical_between_trees=True,
         full_arrays_saved='First and stable density plus RHS only; other lifecycle equality checks were performed in the pinned harness, recorded in JSON.',
         scope='No new far-field solve, ledger test, cross-thread construction rerun, natural tightening occurrence, or timing claim.')
Path(os.environ.get('ANALYSIS_OUT',str(R/'analysis.json'))).write_text(json.dumps(out,indent=2))
print(json.dumps({k:v for k,v in out.items() if k not in ('published_records','fresh')},indent=2))
