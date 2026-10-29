"""32-GB scenario forecasts, kept separate from live-machine admission."""
import json
import os
from pathlib import Path
import sys
from unittest import mock

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT.parent))
os.environ.update(OPENBLAS_NUM_THREADS='4',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4')
from capacity_probe import geometry
from ghost_backend.execution.options import validate_options,execution_scope
from ghost_backend.execution.selection import _forecast_backend
from ghost_backend.twod import solver
import psutil


if __name__=='__main__':
    memory=psutil.virtual_memory()
    report=dict(user_max_frequency_ghz=15,user_ram_ceiling_gib=32,
        observed_machine_total_gib=memory.total/1024**3,observed_available_gib=memory.available/1024**3,
        scope='Initial certification candidates only. Hypothetical budget scenarios, not completed solves or live admission.',
        scenarios=[])
    for name in ('inlet','narrow_inlet','inlet_dielectric','inlet_high_contrast'):
        for budget in (24.,32.):
            options=validate_options(dict(factorization='adaptive',mesh_strategy='adaptive',basis_order=1,
                mesh_grading=True,assembly_threads=4,blas_threads=4,ram_budget_gib=budget,compressed_storage_mib=0))
            args=dict(geometry_snapshot=geometry(name),frequencies_ghz=[15.],elevations_deg=list(range(361)),
                geometry_units='inches',max_panels=100000)
            records=[];row=dict(geometry=name,budget_gib=budget)
            # The model ceiling is the scenario budget. No matrix allocation or
            # numerical solve occurs under this mocked availability.
            with mock.patch.object(solver,'_detect_available_gb',return_value=128.):
                try:
                    selection=_forecast_backend(args,options,certified=True,resource_records=records)
                    row['selection']={k:v for k,v in selection.items() if k!='meshes'}
                except MemoryError as exc:row['admission_error']=str(exc)
                row['resources']=[]
                for resource,settings in records:
                    evidence=dict(resource=resource,basis_order=settings['basis_order'],forecasts={})
                    for mode in ('dense','compressed'):
                        measured=dict(resource)
                        with execution_scope(dict(settings,factorization=mode)):
                            peak=solver._estimate_memory_gb(resource['nodes'],False,n_regions=resource['n_regions'],
                                system_dofs=resource['system_dofs'],operator_matrices=resource['operator_matrices'],
                                dense_resources=measured,n_rhs=361,solver_method='experimental_cpu')
                        evidence['forecasts'][mode]=dict(peak_gib=peak,details=measured.get('memory_estimate'))
                    row['resources'].append(evidence)
            row['max_initial_unknowns']=max(r[0]['system_dofs'] for r in records)
            row['initial_peak_gib']={mode:max(r['forecasts'][mode]['peak_gib'] for r in row['resources']) for mode in ('dense','compressed')}
            report['scenarios'].append(row)
            (HERE/'capacity_15ghz.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            print(json.dumps({k:row[k] for k in ('geometry','budget_gib','max_initial_unknowns','initial_peak_gib')}),flush=True)
