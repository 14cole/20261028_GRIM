import pathlib,json,numpy as np,statistics
D=pathlib.Path(__file__).parent;C=D/'claude_reference';records=[json.loads(x) for x in (C/'nf.jsonl').read_text().splitlines()];checks=[]
def compare(a,b):
 x=np.load(C/'fields'/(a+'.npy'));y=np.load(C/'fields'/(b+'.npy'));assert x.shape==y.shape and np.isfinite(x).all() and np.isfinite(y).all()
 checks.append(dict(case=a,reference=b,relative_max=float(np.max(abs(x-y))/np.max(abs(y))),bitwise_equal=bool(np.array_equal(x,y)),count=x.size))
for body in ['pec8000','diel4000','coated4080','airfoilf3']:
 compare('dense-'+body+'-new-0','dense-'+body+'-old-0')
 compare('densedisk-'+body+'-new','dense-'+body+'-new-0')
 compare('dense-'+body+'-new-1','dense-'+body+'-new-0')
for body in ['diel','coated']:
 for radius in ['100','1','0.01']:
  for tree in ['old','new']:compare(f'scale-{body}-r{radius}-dense-{tree}',f'scale-{body}-r100-dense-{tree}')
for radius in ['100','0.01']:
 for tree in ['old','new']:compare(f'tile-diel-r{radius}-compressed-{tree}',f'tile-diel-r{radius}-dense-{tree}')
for r in records:
 tag=r['tag']
 if tag.startswith('comp-') and '-new' in tag:compare(tag,tag.replace('-new','-old'))
result=dict(claude_commit='c4204e7410af8f204f9b6ee56467feaa95868825',verified_blobs=80,solves=len(records),errors=[r for r in records if r.get('error')],checks=checks)
(D/'CLAUDE_RECOMPUTED.json').write_text(json.dumps(result,indent=2)+'\n');print('solves',len(records),'comparisons',len(checks),'errors',len(result['errors']))
