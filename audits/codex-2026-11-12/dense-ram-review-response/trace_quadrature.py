"""Trace actual quadrature dispatch on the unmodified certified airfoil solve."""
import sys,json,collections,threading,time
from pathlib import Path
import numpy as np
root,out=sys.argv[1:3];sys.path.insert(0,str(Path(root)/'tools/GHOST'))
from ghost_backend.twod import solver as S,polynomial_quadrature as P,operators as O
from ghost_backend.twod.assembly.native import far as F
from ghost_backend.geometry.io import parse_geometry,build_geometry_snapshot
counts=collections.Counter();lock=threading.Lock()
def note(key):
 with lock:counts[key]+=1
moments=P._moments
def wrapped_moments(tasks,pairs,k,obs_derivative,order,*args,**kwargs):
 note('near_moment_order_'+str(order));return moments(tasks,pairs,k,obs_derivative,order,*args,**kwargs)
P._moments=wrapped_moments
block=P.block
def wrapped_block(obs,src,k,obs_derivative=True,order=24,*args,**kwargs):
 note('scalar_block_order_'+str(order));return block(obs,src,k,obs_derivative,order,*args,**kwargs)
P.block=wrapped_block
far=F.far_block
def wrapped_far(table,k,obs_pts,src_pts,weights,phi,*args,**kwargs):
 note('native_far_order_'+str(obs_pts.shape[1])+'_phi_shape_'+str(tuple(phi.shape)))
 return far(table,k,obs_pts,src_pts,weights,phi,*args,**kwargs)
F.far_block=wrapped_far
# Native attempts may return None: count accepted calls separately.
original_wrapped=F.far_block
def accepted_far(*args,**kwargs):
 r=original_wrapped(*args,**kwargs)
 note('native_far_accepted' if r is not None else 'native_far_declined')
 return r
F.far_block=accepted_far
fallback=O._far_tile_numpy
def wrapped_fallback(*args,**kwargs):
 note('numpy_far_calls');return fallback(*args,**kwargs)
O._far_tile_numpy=wrapped_fallback
g=build_geometry_snapshot(*parse_geometry((Path(root)/'airfoil.geo').read_text()))
t=time.perf_counter()
r=S.solve_monostatic_rcs_2d_certified(g,[3.],list(np.linspace(0,180,181)),geometry_units='inches',max_panels=200000,execution_options=dict(factorization='automatic',mesh_strategy='adaptive',assembly_threads='auto',blas_threads='auto'))
m=r['metadata'];a=np.array([complex(v['rcs_amp_real'],v['rcs_amp_imag']) for v in r['samples']])
np.savez(out+'.npz',field=a);Path(out+'.metadata.json').write_text(json.dumps(m,default=str))
d=dict(runtime_pin='d162169876cf53d10ca0f1b7382c94ba5301fb82',wall_seconds=time.perf_counter()-t,counts=dict(sorted(counts.items())),certified=m.get('mesh_convergence_certified'),degree=m.get('polynomial_degree'),warnings=m.get('warnings'),quality_gate=m.get('quality_gate'),adaptive_steps=m.get('adaptive_mesh',{}).get('steps'))
Path(out+'.json').write_text(json.dumps(d,indent=2,default=str)+'\n');print(json.dumps(d,default=str))
