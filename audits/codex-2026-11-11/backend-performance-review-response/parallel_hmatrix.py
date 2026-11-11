"""Actual two-worker Automatic H-matrix sweep below the explicit 8192 threshold."""
import json,sys
from pathlib import Path
import numpy as np
from plan_probe import arguments
from ghost_backend.execution.options import automatic_options,execution_scope
from ghost_backend.execution.fresh_sweep import run_fresh
from ghost_backend.twod import solver as S
def main():
    args=arguments(8000)
    opts=dict(automatic_options(3.56),mesh_strategy='global',assembly_threads='auto',blas_threads='auto')
    records=[]; fields={}
    for workers in (1,2):
        with execution_scope(opts,assembly_threads=4,memory_budget_gib=3.56):
            r=run_fresh(S.solve_monostatic_rcs_2d_survey,args,opts,'double',False,frequency_workers=workers)
        m=r['metadata']; ex=m['frequency_execution']; per=[x['metadata'] for x in m['frequency_metadata']]
        assert ex['mode']==('sequential' if workers==1 else 'parallel'),ex
        if workers==2:
            assert ex['maximum_active_workers']==2 and ex['units_lost_to_worker_failure']==0,ex
            # peak_reserved_gib already includes interpreter reservations.
            assert ex['peak_reserved_gib']<=ex['memory_budget_gib'],ex
            for meta in per:
                assert meta['linear_backend']=='cpu_hmatrix',meta['linear_backend']
                assert meta['backend_selection']['automatic_policy']
                assert meta['backend_selection']['selected']=='compressed'
                assert meta['frequency_worker']['cpus']==2
        assert all(x['quality_gate']['passed'] for x in per)
        fields[str(workers)]=np.array([complex(x['rcs_amp_real'],x['rcs_amp_imag']) for x in r['samples']])
        records.append(dict(workers=workers,execution=ex,per_frequency=per))
        print('workers',workers,ex,[x['linear_backend'] for x in per],flush=True)
    error=float(max(abs(fields['1']-fields['2']))/max(abs(fields['1'])))
    assert error<1e-8,error
    p=Path(__file__).parent
    (p/'parallel-hmatrix-results.json').write_text(json.dumps(dict(norm_scaled_error=error,runs=records),default=str,indent=2)+'\n')
    np.savez_compressed(p/'parallel-hmatrix-fields.npz',**fields)
    print('PASS',error,flush=True)
if __name__=='__main__':main()
