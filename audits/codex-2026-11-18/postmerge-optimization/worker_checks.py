import os,sys,pathlib,json,threading,numpy as np
root=pathlib.Path(__file__).resolve().parent;repo=pathlib.Path(os.environ.get('NEW_GRIM_ROOT',root/'candidate'));ghost=repo/'tools/GHOST'
sys.path[:0]=[str(repo),str(ghost)]
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtCore import QCoreApplication
from ghost_backend.ui.solver import _SolveWorker,_result_sample_counts,_result_rows
from collections import Counter
from ghost_backend.geometry.io import parse_geometry,build_geometry_snapshot
from ghost_backend.runs.setup import two_d_request
app=QCoreApplication([]);records=[]
for name in ('type2_pec','type3_magnetic_dielectric'):
 path=ghost/'ghost_backend/geometry/geometries/material_examples'/(name+'.geo')
 snapshot=build_geometry_snapshot(*parse_geometry(path.read_text()))
 for method in ('dense','compressed'):
  abort=threading.Event()
  request=two_d_request([1.0],list(range(-90,90)),'meters',False,'standard','monostatic',[],controls=dict(factorization=method,mesh_strategy='global',basis_order=1,mesh_grading=False))
  options=dict(request['execution_options'],assembly_threads=2,blas_threads=1,ram_budget_gib=4)
  worker=_SolveWorker(snapshot=snapshot,source_path=str(path),base_dir=str(path.parent),frequencies=request['frequencies_ghz'],elevations=request['angles_deg'],units=request['units'],quality_thresholds={},mesh_certification=False,abort_event=abort,solver_method=request['solver_method'],execution_options=options)
  results=[];errors=[];canceled=[]
  worker.finished.connect(lambda result,path:results.append(result));worker.error.connect(errors.append);worker.canceled.connect(canceled.append)
  worker.run()
  assert len(results)==1 and not errors and not canceled,(name,method,errors,canceled)
  counts=_result_sample_counts(results[0]);print(name,method,counts,flush=True)
  assert counts['incidence_count']==counts['observation_count']==180,counts
  channels=Counter(row['polarization'] for row in _result_rows(results[0]))
  assert channels=={'VV':180,'HH':180},channels
  records.append(dict(geometry=name,method=method,counts=counts,metadata=results[0]['metadata']))
  abort.set();worker.run();assert len(canceled)==1 and len(results)==1 and not errors
(root/'worker-checks.json').write_text(json.dumps(records,indent=2,default=str))
print('PASS four desktop worker solves, both polarizations, 180 monostatic angles; four pre-canceled requests',flush=True)
