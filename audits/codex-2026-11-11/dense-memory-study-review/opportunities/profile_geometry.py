"""Same square geometry, different primitive fragmentation and hp choices."""
import sys,json,time,math
from pathlib import Path
import numpy as np
root,spec=sys.argv[1],json.loads(sys.argv[2]);sys.path.insert(0,str(Path(root)/'tools/GHOST'))
from ghost_backend.geometry.io import parse_geometry,build_geometry_snapshot
from ghost_backend.twod import solver as S
from ghost_backend.linalg.dense import DenseFactor
vertices=[(0.,0.),(0.,1.),(1.,1.),(1.,0.),(0.,0.)]
parts=spec['parts'];lines=[]
for a,b in zip(vertices[:-1],vertices[1:]):
 xy=np.linspace(a,b,parts+1)
 for c,d in zip(xy[:-1],xy[1:]):lines.append('%.17g %.17g %.17g %.17g'%(*c,*d))
g=build_geometry_snapshot(*parse_geometry('Title: exact square\nSegment: b 2\nproperties: 2 -'+str(spec['ppw'])+' 0 0 0\n'+'\n'.join(lines)+'\nIBCS_Resistances:\nDielectrics:\n'))
if spec.get('coarsening'):g['_2d_hp_coarsening']=spec['coarsening']
factors=[];init=DenseFactor.__init__
def wrapped(self,a,*args,**kwargs):
 factors.append(dict(n=len(a),matrix_bytes=a.nbytes));return init(self,a,*args,**kwargs)
DenseFactor.__init__=wrapped
start=time.perf_counter();error=None;r=None
try:
 r=S.solve_monostatic_rcs_2d_survey(g,[.6],list(np.linspace(0,180,91)),geometry_units='meters',max_panels=30000,execution_options=dict(factorization='dense',assembly_threads=4,blas_threads=4,dense_residual_storage='disk',basis_order=spec.get('degree',1)))
except Exception as e:error=type(e).__name__+': '+str(e)
d=dict(spec,wall=time.perf_counter()-start,error=error,factors=factors,geometry_perimeter=4.,geometry_area=1.)
if r:
 a=np.array([complex(v['rcs_amp_real'],v['rcs_amp_imag']) for v in r['samples']]);np.savez(spec['out'],field=a)
 Path(spec['out']+'.metadata.json').write_text(json.dumps(r['metadata'],default=str))
 d['quality_gate']=r['metadata'].get('quality_gate')
print(json.dumps(d,default=str))
