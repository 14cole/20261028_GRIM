"""Public survey entry point, both backends and PEC/dielectric geometries."""
import os,sys,json,time,resource
from pathlib import Path
import numpy as np
sys.path.insert(0,os.environ['GRIM_ROOT']+'/tools/GHOST')
from ghost_backend.geometry.io import parse_geometry,build_geometry_snapshot
from ghost_backend.twod.solver import solve_monostatic_rcs_2d_survey
from ghost_backend.execution.options import cpu_allocation_scope
spec=json.loads(sys.argv[1]);n=64;t=-np.linspace(0,2*np.pi,n+1);xy=np.c_[np.cos(t),np.sin(t)];xy[-1]=xy[0]
segments='\n'.join('%.15g %.15g %.15g %.15g'%(*xy[i],*xy[i+1]) for i in range(n))
props='2 1 0 0 0' if spec['body']=='pec' else '3 1 0 1 0'
materials='' if spec['body']=='pec' else '1 3.0 -0.08 1.0 0.0'
text=f'Title: smoke\nSegment: b {props[0]}\nproperties: {props}\n{segments}\nIBCS_Resistances:\nDielectrics:\n{materials}\n'
g=build_geometry_snapshot(*parse_geometry(text));start=time.perf_counter()
with cpu_allocation_scope(4):
 r=solve_monostatic_rcs_2d_survey(g,[.190853806369],list(np.linspace(0,180,9)),geometry_units='meters',execution_options={'factorization':spec['mode'],'assembly_threads':spec.get('threads',1),'blas_threads':1,'basis_order':spec.get('order',1)},max_panels=4096)
assert r['samples']
Path(spec['out']+'.json').write_text(json.dumps(dict(spec,seconds=time.perf_counter()-start,peak_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20,result=r)))
np.savez_compressed(spec['out']+'.npz',field=np.array([complex(s['rcs_amp_real'],s['rcs_amp_imag']) for s in r['samples']]))
