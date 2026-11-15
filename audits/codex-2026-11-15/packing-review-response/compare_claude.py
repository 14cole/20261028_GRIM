"""Compare fresh arrays with Claude's published hashes (not a tolerance test)."""
import hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent
index=json.loads((P/'claude/density_index.json').read_text())
pairs={
 'partialTE-dense-none':'c-hard-partial-TE-dense-non',
 'partialTE-compressed-none':'c-hard-partial-TE-compressed-non',
 'partialTE-compressed-bounded':'d-hard-partial-TE-compressed-relaxed-constructio',
 'multilayerTM-dense-none':'c-hard-multilayer-TM-dense-non',
 'multilayerTM-compressed-none':'c-hard-multilayer-TM-compressed-non',
 'multilayerTM-compressed-bounded':'d-hard-multilayer-TM-compressed-relaxed-constructio',
 'multilayerTM-cap675-bounded':'e-cap675-multilayer-TM-compressed-relaxed-constructio',
 'multilayerTE-bounded':'d-hard-multilayer-TE-compressed-relaxed-constructio',
}
records=[]
for label,ref in pairs.items():
    p=P/'results'/(label+'-solve0000.npz')
    if not p.exists():
        records.append(dict(case=label,reference=ref,status='no captured density'));continue
    with np.load(p) as z:
        for key in ('density','rhs'):
            a=z[key];h=hashlib.sha256(a.tobytes(order='C')).hexdigest()
            records.append(dict(case=label,reference=ref,array=key,shape=list(a.shape),
                sha256=h,claude_sha256=index[ref][key]['sha256'],
                matches=bool(h==index[ref][key]['sha256'] and list(a.shape)==index[ref][key]['shape'])))
out=dict(evidence='Fresh solves compared with published C-order array byte hashes; no downloaded Claude density arrays or new equation evaluations.',records=records)
(P/'claude-array-hash-comparison.json').write_text(json.dumps(out,indent=2))
print('Published-hash matches:',sum(x.get('matches',False) for x in records),'of',len(records))
