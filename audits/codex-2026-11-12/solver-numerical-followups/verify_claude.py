"""Recompute quoted field differences from the pinned Claude arrays."""
import json,pathlib,numpy as np
D=pathlib.Path(__file__).parent;R=D/'claude_reference';F=R/'fields'
def difference(a,b):
 x,y=np.load(F/(a+'.npy')),np.load(F/(b+'.npy'))
 assert x.shape==y.shape and np.isfinite(x).all() and np.isfinite(y).all()
 return float(np.max(abs(x-y))/np.max(abs(y)))
checks=[]
for body in ['diel','coated','pec']:
 for radius in ['100','1','0.05','0.01']:
  a=f'scale-{body}-r{radius}-compressed';b=f'scale-{body}-r{radius}-dense';ref=f'scale-{body}-r100-dense'
  checks.append(dict(body=body,radius=radius,compressed_dense=difference(a,b),dense_large=difference(b,ref),compressed_large=difference(a,ref)))
ordinary=[]
for body in ['diel4000','coated4080','airfoilf3','pec8000']:
 for label in ['old','new']:
  ordinary.append(dict(case=f'time-{body}-{label}-0',relative_max=difference(f'time-{body}-{label}-0',f'ref-{body}-dense')))
rows=[json.loads(line) for line in (R/'wfi.jsonl').read_text().splitlines()]
summary=dict(claude_commit='095df528656718130e712918c0281d07edaf4cd8',verified_blobs=63,recorded_solves=len(rows),runtime_errors=[r for r in rows if r.get('error')],field_arrays=len(list(F.glob('*.npy'))),scale_checks=checks,ordinary_checks=ordinary)
(D/'CLAUDE_RECOMPUTED.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
