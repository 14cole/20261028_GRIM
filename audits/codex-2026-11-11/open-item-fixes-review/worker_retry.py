"""Natural rank-limit rejection and recovery inside two spawned frequency workers."""
import sys,json,math
from pathlib import Path
import numpy as np
from retry_workflows import geometry
from ghost_backend.execution.options import execution_scope
from ghost_backend.execution.fresh_sweep import run_fresh
from ghost_backend.twod import solver as S
def main():
    n=8000; f=.314/(2*math.pi/n)*299792458/(2*math.pi)/1e9
    opts=dict(factorization='compressed',mesh_strategy='global',assembly_threads='auto',blas_threads='auto',ram_budget_gib=8.)
    args=dict(geometry_snapshot=geometry(n),frequencies_ghz=[.9*f,f],elevations_deg=[0.,45.,90.],geometry_units='meters',max_panels=100000)
    with execution_scope(opts,assembly_threads=4,memory_budget_gib=8.):
        r=run_fresh(S.solve_monostatic_rcs_2d_survey,args,opts,'double',False,frequency_workers=2)
    m=r['metadata'];ex=m['frequency_execution'];assert ex['mode']=='parallel' and ex['maximum_active_workers']==2,ex
    assert ex['units_lost_to_worker_failure']==0 and ex['peak_reserved_gib']<=8.,ex
    per=[x['metadata'] for x in m['frequency_metadata']]
    for x in per:
        assert x['quality_gate']['passed'] and x['linear_backend']=='cpu_hmatrix'
        assert x.get('compressed_hmatrix_retry') and x['frequency_worker']['cpus']==2
        assert x['execution_memory_reservation_gib']==x['frequency_worker']['memory_reservation_gib']
    a=np.array([complex(s['rcs_amp_real'],s['rcs_amp_imag']) for s in r['samples']])
    here=Path(__file__).parent
    with np.load(here/'worker-reference-fields.npz') as z:b=z['1']
    assert len(a)==len(b)==12
    err=float(max(abs(a-b))/max(abs(b)));assert err<1e-8,err
    (here/'worker-retry-results.json').write_text(json.dumps(dict(execution=ex,relative_error=err,per_frequency=per),default=str,indent=2)+'\n')
    np.savez_compressed(here/'worker-retry-fields.npz',actual=a,reference=b)
    print('PASS: natural rejection/retry in two spawned workers',ex,'relative error',err,flush=True)
if __name__=='__main__':main()
