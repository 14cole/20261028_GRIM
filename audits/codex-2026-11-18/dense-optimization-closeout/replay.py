"""Independent replay of the pinned review; no solver execution."""
import json, pathlib, hashlib
import numpy as np
r=pathlib.Path(__file__).resolve().parent
c=r/'claude'
out={'review_commit':'4efea5f0579cff2e4907c4a88aa4118408c87fb7'}
def rel(x,y):
    return float(np.max(np.abs(x-y))/max(float(np.max(np.abs(y))),1e-300))
cases={};groups={};fields={}
for name,spec in json.loads((c/'claude_X.json').read_text()):
    d=json.loads((c/'results'/f'{name}.json').read_text())
    t=json.loads((c/'results'/f'{name}.time.json').read_text())
    assert t['returncode']==0 and d['error'] is None and d['metadata']['quality_gate']['passed']
    assert all(p['threads']==spec['threads'] for p in d['hooks']['pools_in_solve'])
    assert all(e['refinement_steps']==1 for e in d['hooks']['dense_events'])
    seconds=sum(g['solve_seconds'] for g in d['hooks']['dense_gate'])
    with np.load(c/'results'/f'{name}-fields.npz') as z:
        f=z['field'];assert f.shape==(180,) and np.isfinite(f).all();fields[name]=f.copy()
    key=f"b{spec['batch']}-t{spec['threads']}"
    groups.setdefault(key,{}).setdefault(spec['tree'],[]).append(seconds)
    cases[name]={'solve_seconds':seconds,'wall_seconds':d['wall_seconds'],'tree':spec['tree']}
assert len(cases)==28 and sum(v['tree']=='direct' for v in cases.values())==10
comparisons={}
for name,field in fields.items():
    ref=name.replace('-direct-','-main-').replace('-numpyF-','-main-')
    error=rel(field,fields[ref]);assert error<1e-10
    comparisons[name]={'reference':ref,'field_peak_relative':error}
for key,g in groups.items():
    base=float(np.median(g['main']))
    groups[key]={'times':g,'median_seconds':{v:float(np.median(a)) for v,a in g.items()},'change_percent':{v:100*(float(np.median(a))/base-1) for v,a in g.items()}}
out['physical']={'count':28,'direct_count':10,'groups':groups,'comparisons':comparisons,'cases':cases}
hashes=json.loads((c/'density_hashes.json').read_text());densities={}
for p in (c/'densities').glob('*.npz'):
    name=p.name.removesuffix('-density.npz')
    with np.load(p) as z:
        a=z['density'];assert a.shape==(4146,180) and np.isfinite(a).all()
        h=hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest();assert h==hashes[name]['sha256']
        densities[name]=a.copy()
base=densities['x-main-b16-t4-0']
out['densities']={n:{'peak_relative_to_main_t4':rel(a,base),'frobenius_relative_to_main_t4':float(np.sqrt(np.sum(abs(a-base)**2)/np.sum(abs(base)**2)))} for n,a in densities.items()}
assert len(densities)==3
storage={}
for name,spec in json.loads((c/'claude_Y.json').read_text()):
    d=json.loads((c/'results'/f'{name}.json').read_text());b=d['hooks']['operator_breakdown'];assert len(b)==1;b=b[0]
    keys=['exact_near_bytes','dense_far_bytes','lowrank_far_bytes','sample_row_bytes']
    other=b['retained_bytes']-sum(b[k] for k in keys)
    assert 0<=other<b['retained_bytes']*.01,(name,other)
    assert b['evidence_near_bytes']==b['exact_near_bytes']+b['dense_far_bytes']
    assert b['evidence_far_bytes']==b['lowrank_far_bytes']
    failed=name=='y-multilayer-TM-1.2m'
    t=json.loads((c/'results'/f'{name}.time.json').read_text());assert t['returncode']==(2 if failed else 0)
    if failed:assert 'condition_est_max' in d['error']
    else:
        assert d['error'] is None and d['metadata']['quality_gate']['passed']
        with np.load(c/'results'/f'{name}-fields.npz') as z:assert np.isfinite(z['field']).all() and z['field'].shape==(180,)
    inv=d['factors'][0]['preconditioners'][-1]['bytes']
    storage[name]={'unknowns':b['unknowns'],'mib':{k:b[k]/2**20 for k in keys},'share':{k:b[k]/b['retained_bytes'] for k in keys},'other_retained_bytes':other,'other_share':other/b['retained_bytes'],'operator_mib':b['retained_bytes']/2**20,'inverse_mib':inv/2**20,'peak_gib':d['peak_gib'],'condition_gate_failed':failed}
out['storage']=storage
out['all_replay_checks_passed']=True
(r/'replay.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'groups':groups,'densities':out['densities'],'storage':storage,'all_pass':True},indent=2))
