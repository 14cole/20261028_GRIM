"""Read-only primitive scan; candidates are not authorization to alter a model."""
import sys,json
from pathlib import Path
import numpy as np
root=sys.argv[1];sys.path.insert(0,str(Path(root)/'tools/GHOST'))
from ghost_backend.geometry.io import parse_geometry,build_geometry_snapshot
g=build_geometry_snapshot(*parse_geometry((Path(root)/'airfoil.geo').read_text()))
rows=[]
for seg in g['segments']:
 pairs=seg['point_pairs'];count=0
 for left,right in zip(pairs[:-1],pairs[1:]):
  a=np.array([left['x1'],left['y1']],float);b=np.array([left['x2'],left['y2']],float)
  c=np.array([right['x1'],right['y1']],float);d=np.array([right['x2'],right['y2']],float)
  u=b-a;v=d-c
  if np.array_equal(b,c) and u[0]*v[1]-u[1]*v[0]==0. and u@v>0:count+=1
 rows.append(dict(name=seg['name'],primitives=len(pairs),properties=seg['properties'],exact_collinear_internal_candidates=count))
print(json.dumps(dict(file='airfoil.geo',segments=len(rows),primitives=sum(r['primitives'] for r in rows),exact_collinear_internal_candidates=sum(r['exact_collinear_internal_candidates'] for r in rows),rows=rows),indent=2))
