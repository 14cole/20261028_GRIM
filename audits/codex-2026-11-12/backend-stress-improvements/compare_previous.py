"""Compare full complex samples by physical keys to the archived previous suite."""
import json,sys
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent
OLD=Path(sys.argv[1])
rows=[]
for f in sorted((P/'results').glob('*.samples.json')):
    name=f.name.removesuffix('.samples.json');old=OLD/'results'/f.name
    if not old.exists():continue
    def samplemap(path):
        return {(r['frequency_ghz'],r['theta_inc_deg'],r['polarization_internal']):complex(r['rcs_amp_real'],r['rcs_amp_imag']) for r in json.loads(path.read_text())}
    a,b=samplemap(old),samplemap(f);assert a.keys()==b.keys(),name
    keys=sorted(a);x=np.array([a[k] for k in keys]);y=np.array([b[k] for k in keys]);assert np.isfinite(y).all()
    rows.append(dict(case=name,fields=len(keys),bitwise_equal=bool(np.array_equal(x,y)),relative_max_difference=float(max(abs(x-y))/max(abs(x)))))
changes=[]
for f in sorted((P/'results').glob('*.json')):
    if f.name.endswith(('.samples.json','.metadata.json','.monitor.json')):continue
    old=OLD/'results'/f.name
    if not old.exists():continue
    a,b=json.loads(old.read_text()),json.loads(f.read_text())
    if (a['error'] or '').split(':')[0]!=(b['error'] or '').split(':')[0]:changes.append(dict(case=b['spec']['case'],before=a['error'],after=b['error']))
out=dict(compared_cases=len(rows),compared_fields=sum(r['fields'] for r in rows),worst_relative_max_difference=max([r['relative_max_difference'] for r in rows]or[0]),outcome_changes=changes,rows=rows)
(P/'PREVIOUS_COMPARISON.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='rows'},indent=2))
