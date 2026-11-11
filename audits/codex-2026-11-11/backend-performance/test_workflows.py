"""Real solves across explicit/automatic policies, mesh workflows and memory limits."""
import json,math,os,sys
from pathlib import Path
from unittest.mock import patch
import numpy as np
root=Path(sys.argv[1]);sys.path.insert(0,str(root/'tools/GHOST'))
from ghost_backend.geometry.io import parse_geometry,build_geometry_snapshot
from ghost_backend.twod import solver as S
from ghost_backend.execution.options import automatic_options,execution_scope
from ghost_backend.execution.selection import select_backend
from ghost_backend.execution import timing_history
out=Path(__file__).resolve().parent;records=[]
def circle(n=128,r=.1):
    t=-np.linspace(0,2*np.pi,n+1);p=[(r*np.cos(a),r*np.sin(a)) for a in t];p[-1]=p[0]
    rows='\n'.join('%.15g %.15g %.15g %.15g'%(*p[i],*p[i+1]) for i in range(n))
    return build_geometry_snapshot(*parse_geometry('Title: t\nSegment: b 2\nproperties: 2 1 0 0 0\n'+rows+'\nIBCS_Resistances:\nDielectrics:\n'))
g=circle();angles=[0.,37.,90.]
for strategy in ('global','local','adaptive'):
 for checked in (False,True):
    options=dict(automatic_options(),mesh_strategy=strategy,assembly_threads=1,blas_threads='auto')
    fn=S.solve_monostatic_rcs_2d_certified if checked else S.solve_monostatic_rcs_2d_survey
    with patch.object(timing_history,'read',side_effect=AssertionError('automatic read timing history')),patch.object(timing_history,'record',side_effect=AssertionError('automatic wrote timing history')):
        r=fn(g,[.3],angles,geometry_units='meters',execution_options=options)
    m=r['metadata'];assert m['quality_gate']['passed']
    assert m['mesh_convergence_certified']==checked,(strategy,checked,m)
    records.append(dict(case=strategy+('-certified' if checked else '-survey'),samples=len(r['samples']),
        certified=m['mesh_convergence_certified'],backend=m.get('linear_backend'),
        selection=m.get('backend_selection'),adaptive_mesh=m.get('adaptive_mesh')))
# Real low-memory selection on a larger fixed mesh; do not run with a fake budget.
glarge=circle(4000,1.)
freq=.314/(2*np.pi/4000)*299792458./(2*np.pi)/1e9
args=dict(geometry_snapshot=glarge,frequencies_ghz=[freq],elevations_deg=angles,geometry_units='meters',max_panels=100000)
base_opts=dict(automatic_options(),mesh_strategy='global',assembly_threads=1,blas_threads='auto')
selection=select_backend(args,base_opts)
dense_peak=selection['candidates']['dense']['peak_gb'];compressed_peak=selection['candidates']['compressed']['peak_gb']
budget=(dense_peak+compressed_peak)/2
assert compressed_peak<budget<dense_peak,(dense_peak,compressed_peak)
small_opts=dict(base_opts,ram_budget_gib=budget)
r=S.solve_monostatic_rcs_2d_survey(**args,execution_options=small_opts)
assert r['metadata']['backend_selection']['selected']=='compressed'
assert r['metadata']['linear_backend']=='cpu_hmatrix'
records.append(dict(case='limited-ram-hmatrix',budget=budget,unlimited_forecast=selection,
    selection=r['metadata']['backend_selection'],backend=r['metadata']['linear_backend']))
# An admitted numerical failure may retry, but explicit requests cannot switch.
from ghost_backend.linalg.dense import DenseFactor
original=DenseFactor.__init__
def reject(*a,**kw):raise np.linalg.LinAlgError('injected factor rejection')
with patch.object(DenseFactor,'__init__',reject):
    r=S.solve_monostatic_rcs_2d_survey(g,[.3],angles,geometry_units='meters',execution_options=dict(base_opts,factorization='automatic'))
assert r['metadata']['backend_selection']['selected']=='compressed'
assert r['metadata']['backend_selection']['failed_attempts']
with patch.object(DenseFactor,'__init__',reject):
    try:S.solve_monostatic_rcs_2d_survey(g,[.3],angles,geometry_units='meters',execution_options=dict(base_opts,factorization='dense'))
    except np.linalg.LinAlgError:pass
    else:raise AssertionError('explicit dense silently switched')
records.append(dict(case='admitted-retry-and-fixed-override',passed=True))
# Saved UI policy and mesh workflow remain independent.
from PySide6.QtWidgets import QApplication
from ghost_backend.ui.twod_options import TwoDOptionsWidget
app=QApplication.instance() or QApplication([]);w=TwoDOptionsWidget()
assert w.value()['factorization']=='automatic'
for mode in ('automatic','dense','compressed','adaptive','hierarchical'):
    w.set_value(dict(factorization=mode,mesh_strategy='global',basis_order=2,mesh_grading=False))
    w.set_automatic_mesh(True);assert w.value()['factorization']==mode
    w.set_automatic_mesh(False);assert w.value()['factorization']==mode and w.value()['basis_order']==2
records.append(dict(case='ui-roundtrip-five-policies',passed=True))
(out/'workflow-results.json').write_text(json.dumps(records,indent=2,default=str)+'\n')
print('PASS',len(records),'workflow groups')
