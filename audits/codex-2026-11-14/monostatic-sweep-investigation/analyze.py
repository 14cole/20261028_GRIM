"""Recompute comparisons from all saved complex arrays; never compare RCS alone."""
from pathlib import Path
import json,hashlib,os
import numpy as np
from evidence_paths import batches
ROOT=Path(__file__).resolve().parent
RESULTS=Path(os.environ.get('MONOSTATIC_RESULTS',str(ROOT / 'results'))).resolve()
OUTPUT=Path(os.environ.get('MONOSTATIC_ANALYSIS',str(ROOT/'analysis.json'))).resolve()

def arrays(label):
    paths=[] if (RESULTS/(label+'.npz')).is_file() else batches(RESULTS,label)
    blocks=[]
    for path in paths:
        with np.load(path,allow_pickle=False) as z:blocks.append({k:np.ascontiguousarray(z[k]) for k in z.files})
    if not blocks:
        with np.load(RESULTS/(label+'.npz'),allow_pickle=False) as z:blocks=[{k:np.ascontiguousarray(z[k]) for k in z.files}]
    assert all(np.isfinite(v).all() for block in blocks for v in block.values()),label
    a={k:np.concatenate([b[k] for b in blocks],axis=1 if k in ('density','rhs','residual') else 0) for k in ('angles','density','rhs','field','residual')}
    meta=RESULTS/(label+'.json')
    if meta.exists():
        spec=json.loads(meta.read_text())['spec']
        expected=np.linspace(spec.get('start',0),spec.get('stop',360),spec['count'],endpoint=False)
        assert np.array_equal(a['angles'],expected),(label,'missing or incorrect angles')
        assert a['density'].shape==a['rhs'].shape==(2*spec['n'],spec['count']),label
        assert a['field'].shape==(spec['count'],),label
    for b in blocks:
        err=np.max(abs(b['residual'])/(b['row_norm'][:,None]*np.max(abs(b['density']),axis=0)+abs(b['rhs'][b['rows']])),axis=0)
        assert np.isfinite(err).all() and err.max()<1e-12,(label,err)
    return a

def main():
    records={}
    for p in sorted(RESULTS.glob('*.json')):
        if p.name.endswith('.time.json'):continue
        d=json.loads(p.read_text())
        if 'spec' in d and p.with_suffix('.time.json').exists():
            timing=json.loads(p.with_suffix('.time.json').read_text())
            if timing['rc']==0:records[p.stem]=d
    table=[];comparisons=[]
    for label,d in records.items():
        s=d['spec'];aa=d['angles'];e=d.get('event',{}).get('sweep_compression',{})
        table.append(dict(label=label,unknowns=2*s['n'],count=s['count'],method=s['method'],batch=s.get('batch',256),setup=d['setup_seconds'],solve=d['solve_seconds'],field=d['field_seconds'],compute=d['compute_seconds'],wall=d['wall_seconds'],peak=d['peak_gib'],matvecs=sum(a['matvecs'] for a in aa)+sum(z['rhs_equivalent_matrix_applications'] for z in d.get('block_krylov',[]))+(s['count'] if s.get('krylov')=='rhs_qr' else 0),preconditioner_calls=sum(a['preconditioner_calls'] for a in aa)+sum(z.get('preconditioner_rhs_applications',z['preconditioner_applications']*z['columns']) for z in d.get('block_krylov',[])),max_recycle_bytes=max([a['recycle_bytes'] for a in aa],default=0),max_krylov_capacity_bytes=max([z['krylov_vector_capacity_bytes'] for z in d.get('block_krylov',[])],default=0),sweep=e,rhs_qr=d.get('rhs_qr'),inverse_saved_bytes=d.get('inverse_saved_bytes')))
        if s['method']=='dense' and s.get('residual_storage','memory')=='memory' and 'batch' not in label:continue
        ref=None
        for name,r in records.items():
            ss=r['spec']
            if name!=label and ss['method']=='dense' and ss.get('residual_storage','memory')=='memory' and all(s.get(k,v)==ss.get(k,v) for k,v in [('n',None),('k',None),('geometry','star'),('pol','TE'),('count',None),('start',0.),('stop',360.)]):ref=name;break
        if ref is None:
            for name,r in records.items():
                ss=r['spec']
                if name!=label and ss['method']=='dense' and ss.get('residual_storage','memory')=='memory' and all(s.get(k,v)==ss.get(k,v) for k,v in [('n',None),('k',None),('geometry','star'),('pol','TE')]):
                    requested=np.linspace(s.get('start',0),s.get('stop',360),s['count'],endpoint=False)
                    available=np.linspace(ss.get('start',0),ss.get('stop',360),ss['count'],endpoint=False)
                    if all(np.any(available==angle) for angle in requested):ref=name;break
        if ref is None:continue
        a,b=arrays(label),arrays(ref)
        if not np.array_equal(a['angles'],b['angles']):
            ids=np.array([np.flatnonzero(b['angles']==angle)[0] for angle in a['angles']])
            for key in b:b[key]=b[key][:,ids] if key in ('density','rhs','residual') else b[key][ids]
        assert np.array_equal(a['angles'],b['angles']),label
        rhs_difference=a['rhs']-b['rhs']
        rhs_relative=float(np.max(np.linalg.norm(rhs_difference,axis=0)/np.linalg.norm(b['rhs'],axis=0)))
        rhs_peak=float(np.max(abs(rhs_difference))/np.max(abs(b['rhs'])))
        assert rhs_relative<5e-15 and rhs_peak<5e-15,(label,rhs_relative,rhs_peak)
        df=a['field']-b['field'];dx=a['density']-b['density'];norm=max(float(np.max(abs(b['field']))),1e-300)
        per_density=np.linalg.norm(dx,axis=0)/np.linalg.norm(b['density'],axis=0)
        signal=abs(b['field'])>norm*1e-3
        db=float(np.max(abs(20*np.log10(abs(a['field'][signal])/abs(b['field'][signal]))))) if np.any(signal) else None
        c=dict(label=label,reference=ref,rhs_bitwise_equal=np.array_equal(a['rhs'],b['rhs']),rhs_relative_l2_max=rhs_relative,rhs_peak_relative=rhs_peak,field_max_relative=float(np.max(abs(df))/norm),density_relative_l2_max=float(max(per_density)),db_error_above_minus60db=db)
        c['passed']=c['field_max_relative']<1e-8 and c['density_relative_l2_max']<1e-7
        comparisons.append(c)
    angular_checks=[]
    for label,d in records.items():
        s=d['spec']
        if s['method']=='dense' and s['count']==360 and s.get('start',0)==0 and s.get('stop',360)==360:
            a=arrays(label);f=a['field'];power=abs(f)**2
            angular_checks.append(dict(label=label,opposite_angle_field_difference=float(np.max(abs(f-np.roll(f,180)))/np.max(abs(f))),opposite_angle_power_difference=float(np.max(abs(power-np.roll(power,180)))/np.max(power))))
    result=dict(table=table,comparisons=comparisons,angular_checks=angular_checks,failures=[dict(label=p.stem,**json.loads(p.read_text())) for p in sorted(RESULTS.glob('*.time.json')) if json.loads(p.read_text())['rc']!=0])
    OUTPUT.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    assert all(c['passed'] for c in comparisons)
if __name__=='__main__':main()
