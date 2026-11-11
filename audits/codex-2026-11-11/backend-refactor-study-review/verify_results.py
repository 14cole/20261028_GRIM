"""Assert expected regimes, failures and full-angle agreement from fresh or archived evidence."""
import json,sys
from pathlib import Path
import numpy as np
root=Path(sys.argv[1]).resolve();out=root/'results'
files=sorted(out.glob('*.samples.json'))
if files:
    packed={}
    for f in files:
        samples=json.loads(f.read_text());tag=f.name.removesuffix('.samples.json')
        packed[tag+'__values']=np.array([[s[k] for k in ('frequency_ghz','theta_inc_deg','theta_scat_deg','rcs_amp_real','rcs_amp_imag','rcs_db')] for s in samples])
        packed[tag+'__polarizations']=np.array([s['polarization'] for s in samples])
    np.savez_compressed(out/'fields.npz',**packed)
timings=[]
for name in ('timings.jsonl','profile-checks.jsonl','tuned-large.jsonl'):
    timings += [json.loads(line) for line in (out/name).read_text().splitlines()]
assert len(timings)==19
by_tag={r['tag']:r for r in timings};assert len(by_tag)==19
failures={'pec8000-tile','pec8000-gui-profile'}
expected={'dense1':'cpu','dense4':'cpu','tile4':'cpu_compressed','h4b1':'cpu_hmatrix','h4b4':'cpu_hmatrix'}
for tag,r in by_tag.items():
    if tag in failures:
        assert 'Off-diagonal rank exceeds 256' in r['error'],(tag,r)
    else:
        assert r['error'] is None,(tag,r)
        if tag.startswith('pec4000-') and '-r' in tag:
            assert r['linear_backend']==expected[tag.split('-')[1]]
        if tag=='pec10000-hodlr':assert r['linear_backend']=='cpu_hierarchical'
        if tag=='pec10000-lu':assert r['linear_backend']=='cpu'
rows=[]
with np.load(out/'fields.npz',allow_pickle=False) as archive:
    actual={k.removesuffix('__values') for k in archive.files if k.endswith('__values')}
    assert actual==set(by_tag)-failures
    for tag in sorted(actual):
        n=int(tag.split('-')[0][3:])
        reference={4000:'pec4000-dense4-r1',8000:'pec8000-dense',10000:'pec10000-lu'}[n]
        a,b=archive[tag+'__values'],archive[reference+'__values']
        assert a.shape==b.shape==(362,6),(tag,a.shape)
        assert np.all(np.isfinite(a))
        assert np.array_equal(a[:,:3],b[:,:3])
        assert np.array_equal(archive[tag+'__polarizations'],archive[reference+'__polarizations'])
        av,bv=a[:,3]+1j*a[:,4],b[:,3]+1j*b[:,4]
        relative=float(max(abs(av-bv))/max(abs(bv)))
        assert relative<1e-8,(tag,relative)
        rows.append(dict(case=tag,reference=reference,samples=362,relative_amplitude_error=relative,max_db_difference=float(max(abs(a[:,5]-b[:,5])))))
summary=dict(timed_attempts=len(timings),expected_rank_failures=len(failures),successful_field_sets=len(rows),
    amplitudes_checked=sum(r['samples'] for r in rows),max_relative_amplitude_error=max(r['relative_amplitude_error'] for r in rows),comparisons=rows)
(out/'field-comparisons.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='comparisons'}))
