import sys,json,hashlib
from pathlib import Path
import numpy as np
p=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).parent
rows=[json.loads(x) for x in (p/'fingerprints.jsonl').read_text().splitlines()];by={r['case']:r for r in rows};results=[]
for case in ('batch64','combined'):
 for i,(left,right) in enumerate(zip(by['baseline']['fingerprints'],by[case]['fingerprints'])):
  row=dict(case=case,factor=i,matrix_identical=left['matrix_sha256']==right['matrix_sha256'],matrix_reference_hash=left['matrix_sha256'],matrix_candidate_hash=right['matrix_sha256'])
  for label in ('rhs','solution'):
   a=np.memmap(p/'fingerprints'/('baseline.npz.factor'+str(i)+'.'+label+'.raw'),dtype=complex,mode='r')
   b=np.memmap(p/'fingerprints'/(case+'.npz.factor'+str(i)+'.'+label+'.raw'),dtype=complex,mode='r')
   assert a.shape==b.shape
   row[label]=dict(elements=len(a),bitwise_equal=bool(np.array_equal(a,b)),relative_difference=float(np.max(abs(a-b))/np.max(abs(a))))
  results.append(row)
(p/'fingerprint-comparisons.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
