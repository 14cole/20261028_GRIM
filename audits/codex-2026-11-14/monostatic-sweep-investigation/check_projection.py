"""Independent matched-versus-grid projection and periodic direction checks."""
import json,os,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from monostatic import mesh_for,op,dielectric,CPUState,_STATE,cpu_allocation_scope,execution_scope
with _STATE.override(CPUState(kernel_only=True)),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 mesh=mesh_for(128,'slot');angles=np.array([-90.,-47.,0.,33.,89.]);k=3.
 rng=np.random.default_rng(915);x=rng.normal(size=(128,5))+1j*rng.normal(size=(128,5))
 matched=op._farfield_linear_density_many(mesh,x,k,angles,'DLP')+1j*k*op._farfield_linear_density_many(mesh,x,k,angles,'SLP')
 grid=op._farfield_linear_density_many(mesh,x,k,angles,'DLP',projection='grid')+1j*k*op._farfield_linear_density_many(mesh,x,k,angles,'SLP',projection='grid')
 err=float(np.max(abs(matched-np.diag(grid)))/np.max(abs(matched)))
 b=dielectric.rhs_many(mesh,k,angles);periodic=dielectric.rhs_many(mesh,k,angles+360)
 per=float(np.max(abs(b-periodic))/np.max(abs(b)))
 assert err<1e-13 and per<1e-13,(err,per)
 print(json.dumps(dict(matched_vs_grid_diagonal_relative=err,periodic_rhs_relative=per,convention='production incidence is source direction; observe at same angle',production_source='tools/GHOST/ghost_backend/twod/fields.py')))
