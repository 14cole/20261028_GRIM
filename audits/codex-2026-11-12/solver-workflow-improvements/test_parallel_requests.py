import json,sys,math
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
sys.path.insert(0,str(Path(sys.argv[1])/'tools/GHOST'))
from ghost_backend.geometry.io import parse_geometry,build_geometry_snapshot
from ghost_backend.twod import solver as S
from ghost_backend.execution.options import cpu_allocation_scope
n=600;r=.01;t=-np.linspace(0,2*np.pi,n+1);pts=r*np.column_stack((np.cos(t),np.sin(t)));pts[-1]=pts[0]
g='Title: concurrency\nSegment: b 3\nproperties: 3 1 0 1 0\n'+'\n'.join('%.17g %.17g %.17g %.17g'%(*a,*b) for a,b in zip(pts[:-1],pts[1:]))+'\nIBCS_Resistances:\nDielectrics:\n1 4 -.2 1 0\n'
g=build_geometry_snapshot(*parse_geometry(g));f=.314/(2*math.pi*r/n)*299792458/(2*math.pi)/1e9

def solve(thread_setting):
 with cpu_allocation_scope(2):
  r=S.solve_monostatic_rcs_2d_survey(g,[f],[0.,60.,120.],geometry_units='meters',execution_options=dict(factorization='compressed',blas_threads=thread_setting,assembly_threads=2,ram_budget_gib=2.))
 return r
reference=solve('auto');values=lambda r:np.array([complex(s['rcs_amp_real'],s['rcs_amp_imag']) for s in r['samples']])
with ThreadPoolExecutor(2) as pool:results=list(pool.map(solve,['auto',4]))
out=[]
for r in results:
 error=float(np.max(abs(values(r)-values(reference)))/np.max(abs(values(reference))))
 assert r['metadata']['quality_gate']['passed'] and error<1e-10
 out.append(dict(relative_field_difference=error,metadata=r['metadata'],samples=r['samples']))
Path(sys.argv[2]).write_text(json.dumps(out,indent=2,default=str)+'\n')
print('Two overlapping requests agree with serial reference; both gates passed.')
