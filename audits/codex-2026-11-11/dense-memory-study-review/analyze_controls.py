"""Preserve cross-CPU outliers while checking storage/pairing at matched CPUs."""
from pathlib import Path
import sys,json
import numpy as np
p=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).parent
c=p/'controls';names=['four-cpu-airfoil-default','four-cpu-airfoil-memory-unpaired','four-cpu-airfoil-lean']
a=np.load(c/(names[0]+'.npz'))['field'];results=[]
for name in names:
 b=np.load(c/(name+'.npz'))['field'];err=float(np.max(abs(a-b))/np.max(abs(a)))
 results.append(dict(case=name,reference=names[0],relative_error=err,bitwise_equal=bool(np.array_equal(a,b)),threshold=1e-11,passed=err<1e-11))
(p/'cpu-matched-comparisons.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
raise SystemExit(0 if all(r['passed'] for r in results) else 1)
