"""Compare dimensionless amplitudes at equal electrical size, including tighter operator control."""
import json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent;records=[]
def field(case):return np.load(P/'results'/(case+'.npz'))['field']
def difference(a,b):return float(np.max(abs(a-b))/np.max(abs(b)))
for backend in ['dense','compressed']:
 low=field('diel4k-'+backend+'-baseline');high=field('diel15GHz-'+backend+'-baseline')
 records.append(dict(comparison=backend+'_same_electrical_size',relative_max_norm=difference(high,low)))
for variant in ['baseline','inverse32_fast','operator14']:
 a=field('diel15GHz-compressed-'+variant);dense=field('diel15GHz-dense-baseline');base=field('diel15GHz-compressed-baseline')
 records.append(dict(comparison='15GHz_'+variant,relative_max_norm_vs_dense=difference(a,dense),relative_max_norm_vs_compressed=difference(a,base)))
(P/'SCALE_CHECKS.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps(records,indent=2))
