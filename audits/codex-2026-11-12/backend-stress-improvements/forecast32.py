"""Offline capacity what-if, NOT a 32 GiB execution or measured memory claim.

Reprice captured real-mesh resources at an assumed 24 GiB solve reservation,
with adequate disk-backed scratch. No matrix is assembled and no solve runs.
"""
import copy,json,sys
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent
sys.path.insert(0,str(Path(sys.argv[1])/'tools/GHOST'))
from ghost_backend.twod import solver as s
from ghost_backend.execution.options import execution_scope,cpu_allocation_scope
from ghost_backend.execution import dense_memory as dm

rows=[]
for file in sorted((P/'results').glob('20ft-*.json')):
    if file.name.endswith(('.samples.json','.metadata.json','.monitor.json')):continue
    d=json.loads(file.read_text());spec=d['spec']
    if spec.get('group')!='physical' or not d.get('resources'):continue
    r=copy.deepcopy(d['resources'][0]);r.pop('memory_estimate',None)
    options=dict(factorization=spec['backend'],ram_budget_gib=24.,compressed_storage_mib=0,
        assembly_threads='auto',blas_threads='auto',dense_residual_storage='auto')
    with cpu_allocation_scope(4),execution_scope(options),patch.object(s,'_solve_memory_limit_gb',return_value=24.),patch.object(dm,'scratch_available',return_value=(True,None)):
        forecast=s._estimate_memory_gb(r['nodes'],False,system_dofs=r['system_dofs'],
            operator_matrices=r['operator_matrices'],n_rhs=19,solver_method=s.EXPERIMENTAL_METHOD,
            formulation=r['formulation'],dense_resources=r)
    plan=r['memory_estimate']
    rows.append(dict(case=spec['case'],geometry_id=spec['geometry_id'],backend=spec['backend'],
        unknowns=r['system_dofs'],matrix_gib=16*r['system_dofs']**2/2**30,
        assumed_reservation_gib=24.,forecast_gib=forecast,
        peak_fits=forecast<=24.,predicted_payload_fits=plan.get('storage_fits',True),plan=plan))
(P/'FORECAST_32GIB.json').write_text(json.dumps(dict(assumptions=['32 GiB installed, 24 GiB reserved for one solve',
    'Four CPU allocation; adequate disk-backed scratch assumed','Captured geometry and production forecast; no 32 GiB execution',
    'Dense optional partner assembly not added; it is separately admitted'],rows=rows),indent=2)+'\n')
for r in rows:print(r['case'],r['unknowns'],round(r['forecast_gib'],3),r['peak_fits'],r['predicted_payload_fits'])
