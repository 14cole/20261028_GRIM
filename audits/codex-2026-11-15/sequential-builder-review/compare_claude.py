"""Compare fresh array hashes to pinned published hashes; not a new solve."""
import hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent
refs=json.loads((P/'claude/density_index.json').read_text())
mapping={
 'original-cap640':'g-cap640-multilayer-TM-seq-bounde',
 'corrected-cap640':'g-cap640-multilayer-TM-seq-bounde',
 'corrected-none-cap676':'g-cap676-multilayer-TM-seq-non',
 'corrected-cap626-retry':'g-cap626-multilayer-TM-seq-bounde',
 'rank-guard-cap640':'g-cap640-multilayer-TM-seq-bounde',
 'partialTM-thread4-rank-guard':'f-partial-TM-seq-bounde',
}
records=[]
for label,ref in mapping.items():
    with np.load(P/'results'/(label+'-solve0000.npz')) as z:
        for key in ('rhs','density'):
            a=z[key];h=hashlib.sha256(a.tobytes()).hexdigest()
            records.append(dict(case=label,reference=ref,array=key,sha256=h,
                matches=bool(h==refs[ref][key]['sha256'] and list(a.shape)==refs[ref][key]['shape'])))
out=dict(evidence='Fresh-array C-order hashes compared with published hashes; Claude density arrays were not downloaded.',records=records)
(P/'claude-array-comparison.json').write_text(json.dumps(out,indent=2))
print('Published array hashes matched:',sum(x['matches'] for x in records),'/',len(records))
