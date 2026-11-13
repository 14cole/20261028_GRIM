"""Capture genuine BoR modal matrices, exercise shared HODLR directly.
The capture intentionally stops the public mode sweep before factorization.
No public option named hierarchical is passed to BoR.
"""
import os,sys,json,warnings
from pathlib import Path
import numpy as np
sys.path.insert(0,os.environ['GRIM_ROOT']+'/tools/GHOST')
from ghost_backend.geometry.io import parse_geometry,build_geometry_snapshot
from ghost_backend.bor import dispatch,solver,factor as factor_module
from ghost_backend.bor.factor import ModalFactor
from ghost_backend.linalg import hierarchical as hf
from ghost_backend.linalg.products import adjoint_product
from ghost_backend.execution.options import cpu_allocation_scope
class Captured(Exception):pass
captured={}
def capture(matrix,mode,monitor_cond,*args,coordinates=None,**kw):
 captured.update(matrix=np.array(matrix),coordinates=np.array(coordinates),mode=mode)
 raise Captured()
factor_module.ModalFactor=capture
records=[];arrays={}
for kind,count,freq in [('pec',320,1.),('dielectric',160,1.)]:
 t=np.linspace(0,np.pi,count+1);r=.1*np.sin(t);z=.1*np.cos(t)+.015*np.sin(t)**2;r[[0,-1]]=0
 xy=np.c_[r,z];rows='\n'.join('%.15g %.15g %.15g %.15g'%(*xy[i],*xy[i+1]) for i in range(count))
 props='2 1 0 0 0' if kind=='pec' else '3 1 0 1 0';diel='' if kind=='pec' else '1 3 -.08 1 0'
 geometry=build_geometry_snapshot(*parse_geometry(f'Title: asym sphere\nSegment: b {props[0]}\nproperties: {props}\n{rows}\nIBCS_Resistances:\nDielectrics:\n{diel}\n'))
 with warnings.catch_warnings(),cpu_allocation_scope(1):
  warnings.simplefilter('ignore')
  try:dispatch.solve_monostatic_rcs_bor(geometry,[freq],[0.,40.],geometry_units='meters',workers=1,bor_options=dict(factorization='dense'))
  except Captured:pass
 assert 'matrix' in captured
 a,coords,mode=(captured[x] for x in ('matrix','coordinates','mode'));n=len(a)
 os.environ['GHOST_HIERARCHICAL_MIN_UNKNOWNS']='1'
 rng=np.random.default_rng(654);b=rng.normal(size=(n,3))+1j*rng.normal(size=(n,3))
 arrays[kind+'_matrix']=a;arrays[kind+'_coords']=coords;arrays[kind+'_rhs']=b
 baseline={};conditions={};ranks={}
 for version in ['old','new']:
  hf.adjoint_product=(lambda a,b:a.conj().T@b) if version=='old' else adjoint_product
  factor=ModalFactor(a.copy(),int(mode),True,coordinates=coords)
  assert factor.hierarchical is not None, factor.event
  assert not factor.hierarchical.root.leaf
  conditions[version]=factor.condition;ranks[version]=factor.hierarchical.evidence
  for trans in [0,1,2]:
   x=factor.hierarchical.solve(b,trans=trans);mat=[a,a.T,a.conj().T][trans]
   backward=float(np.linalg.norm(mat@x-b,np.inf)/(np.linalg.norm(mat,np.inf)*np.linalg.norm(x,np.inf)+np.linalg.norm(b,np.inf)))
   assert backward<1e-12
   arrays[f'{kind}_{version}_{trans}']=x
   if version=='old':baseline[trans]=x
   records.append(dict(kind=kind,n=n,version=version,trans=trans,backward_error=backward,relative_to_old=float(np.linalg.norm(x-baseline[trans])/np.linalg.norm(x))))
 print(json.dumps(dict(kind=kind,conditions=conditions,evidence=ranks)),file=sys.stderr,flush=True)
 arrays[kind+'_condition']=np.array(list(conditions.values()));assert abs(conditions['old']/conditions['new']-1)<1e-12
np.savez_compressed('results/bor-hierarchical.npz',**arrays)
Path('results/bor-hierarchical.json').write_text(json.dumps(records,indent=2))
