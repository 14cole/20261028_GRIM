import json,sys,math
from pathlib import Path
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(sys.argv[1])/'tools/GHOST'))
from ghost_backend.geometry.io import parse_geometry,build_geometry_snapshot
from ghost_backend.execution.options import cpu_allocation_scope
from ghost_backend.twod.preparation import preparation_scope
from ghost_backend.execution.selection import select_backend
from ghost_backend.twod import solver as S
from ghost_backend.execution import dense_memory as DM
n=2000;t=-np.linspace(0,2*np.pi,n+1);p=.01*np.column_stack((np.cos(t),np.sin(t)));p[-1]=p[0]
text='Title: refresh\nSegment: b 3\nproperties: 3 1 0 1 0\n'+'\n'.join('%.15g %.15g %.15g %.15g'%(*a,*b) for a,b in zip(p[:-1],p[1:]))+'\nIBCS_Resistances:\nDielectrics:\n1 4 -.2 1 0\n'
g=build_geometry_snapshot(*parse_geometry(text));f=.314/(2*math.pi*.01/n)*299792458/(2*math.pi)/1e9
arguments=dict(geometry_snapshot=g,frequencies_ghz=[f],elevations_deg=list(np.linspace(0,180,19)),geometry_units='meters')
options=dict(factorization='automatic',assembly_threads=1,blas_threads=1,compressed_storage_mib=0)
results=[];capacity=[4.];scratch=[True]
with preparation_scope(),cpu_allocation_scope(4),patch.object(S,'_solve_memory_limit_gb',side_effect=lambda *a:capacity[0]),patch.object(DM,'scratch_available',side_effect=lambda *a:(scratch[0],None if scratch[0] else 'injected lost scratch')):
 results.append(select_backend(arguments,options))
 capacity[0]=.85;results.append(select_backend(arguments,options))
 scratch[0]=False;results.append(select_backend(arguments,options))
assert results[0]['selected']=='dense' and results[0]['meshes'][0]['backend_memory_plans']['dense']['residual_storage']=='memory'
assert results[1]['forecast_reused'] and results[1]['selected']=='dense'
assert results[1]['meshes'][0]['backend_memory_plans']['dense']['residual_storage']=='disk'
assert results[2]['forecast_reused'] and results[2]['selected']=='compressed'
assert results[2]['meshes'][0]['backend_memory_plans']['dense']['residual_storage']=='memory'
Path(sys.argv[2]).write_text(json.dumps(results,indent=2)+'\n')
print('Cached geometry repriced: memory Dense -> disk Dense -> compressed after scratch loss.')
