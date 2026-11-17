"""Replay pinned RAM records and complete fresh layout/accuracy arrays."""
import json,hashlib,os
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;C=R/'claude';D=Path(os.environ.get('FRESH_RESULTS',str(R/'fresh')))
read=lambda p:json.loads(p.read_text())
for f in read(R/'source-provenance.json')['files']:
    b=(C/f['path']).read_bytes()
    assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==f['sha']
def arrays(name):
    with np.load(D/(name+'.npz')) as z:return {k:z[k] for k in z.files}
def diff(a,b):
    assert a.shape==b.shape and a.dtype==b.dtype
    return dict(bits_equal=a.tobytes()==b.tobytes(),peak_relative=float(np.max(abs(a-b))/max(np.max(abs(a)),1e-300)))

ram=read(C/'claude_ram_bisect.json');ram_summary={};field_pairs={};count=0
for key,r in ram.items():
    tree,case=key.split('|');passed=[];failed=[]
    for step in r['trail']:
        d=read(C/'ram'/f'{tree}-{case}-ram{step["mib"]}.json');ok=d['error'] is None
        assert ok==step['ok'];count+=1
        if ok:
            assert d['hooks']['builds']==1 and not d['hooks']['storage_rejections']
            assert d['metadata']['quality_gate']['passed'] and len(d['samples'])==180
            passed.append(step['mib'])
        else:
            assert d['hooks']['builds']==0 and 'requires an estimated' in d['error']
            failed.append(step['mib'])
    assert min(passed)==r['lowest_passing_mib'] and max(failed)==r['highest_failing_mib']
    ram_summary[key]=dict(lowest_passing_mib=min(passed),highest_failing_mib=max(failed))
    if tree=='old':
        for budget in passed:
            old=read(C/'ram'/f'old-{case}-ram{budget}.json');new=read(C/'ram'/f'new-{case}-ram{budget}.json')
            fields=lambda d:np.array([complex(x['rcs_amp_real'],x['rcs_amp_imag']) for x in d['samples']])
            v=diff(fields(old),fields(new));widths=sorted(set(x['shape'][1] for x in old['captures']))
            assert old['captures']==new['captures']
            assert old['metadata']['condition_est_max']==new['metadata']['condition_est_max']
            assert v['peak_relative']<1e-12
            if widths!=[1]:assert v['bits_equal']
            field_pairs[f'{case}-{budget}']=dict(v,batch_widths=widths)
assert count==40
for case,limit in [('partial-TE',376),('pec-circle-TE',308)]:
    assert ram_summary['old|'+case]==ram_summary['new|'+case]
    assert ram_summary['old|'+case]['lowest_passing_mib']==limit

old,new,newF=[arrays('claude-'+name) for name in ('old','new','newF')]
reviewer=read(C/'single_column_layout.json');star={}
for key,a in old.items():
    d,e=diff(a,new[key]),diff(a,newF[key]);assert e['bits_equal']
    assert d['bits_equal']==reviewer[key]['new_equals_old']
    assert d['peak_relative']==reviewer[key]['max_rel_diff']
    star[key]=dict(d,newF_bits_equal=e['bits_equal'])

data={name:arrays(name+'-slot') for name in ('old','new','newF')};slot={};accuracy={};hashes={}
matrix_hashes=set()
for name,arr in data.items():
    record=read(D/(name+'-slot.json'));matrix_hashes.add(record['matrix_sha256'])
    assert record['pending_after']==0 and len(record['checks'])==24
    errors=[]
    for entry in record['checks']:
        key=entry['key'];x=arr[key];ref=arr[key+'__dense'];res=arr[key+'__residual'];norm=arr[key+'__row_norm']
        xx=x[:,None] if x.ndim==1 else x;rr=res[:,None] if res.ndim==1 else res
        b=arr['physical_rhs' if key.startswith('physical_') else 'random_rhs'][:,:xx.shape[1]]
        backward=float(np.max(abs(rr)/(norm[:,None]*np.max(abs(xx),axis=0)+abs(b))))
        relative=float(np.linalg.norm(x-ref)/max(np.linalg.norm(ref),1e-300))
        assert np.isfinite(x).all() and backward<1e-12 and relative<1e-7
        errors.append(dict(key=key,backward_error=backward,dense_relative_l2=relative))
    field_errors={}
    for width in (1,2,8):
        v=diff(arr[f'field_w{width}__dense'],arr[f'field_w{width}'])
        assert v['peak_relative']<1e-8;field_errors[str(width)]=v['peak_relative']
    accuracy[name]=dict(checks=len(errors),max_backward_error=max(x['backward_error'] for x in errors),
        max_dense_relative_l2=max(x['dense_relative_l2'] for x in errors),field_peak_normalized_errors=field_errors)
    hashes[name]={k:hashlib.sha256(v.tobytes()).hexdigest() for k,v in arr.items()}
assert len(matrix_hashes)==1
for key,a in data['old'].items():
    if '__' in key or key in ('random_rhs','physical_rhs','angles'):continue
    d,e=diff(a,data['new'][key]),diff(a,data['newF'][key]);assert e['bits_equal']
    assert d['peak_relative']<1e-10
    if not ('_w1' in key or key.endswith('_vector')):assert d['bits_equal']
    slot[key]=dict(d,newF_bits_equal=e['bits_equal'])
out=dict(all_pass=True,pinned_files=47,reviewer_ram_records=count,ram_thresholds=ram_summary,
    replayed_ram_field_pairs=field_pairs,fresh_star_comparisons=star,fresh_slot_comparisons=slot,
    fresh_slot_accuracy=accuracy,slot_array_hashes=hashes,exact_matrix_sha256=next(iter(matrix_hashes)),
    scope='Three fresh reviewer-script runs and three fresh slot runs; RAM bisection is saved-record replay. No performance, OS-pressure or mesh-convergence claim.')
Path(os.environ.get('ANALYSIS_OUT',str(R/'analysis.json'))).write_text(json.dumps(out,indent=2))
print(json.dumps({k:v for k,v in out.items() if k!='slot_array_hashes'},indent=2))
