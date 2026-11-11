"""Compare Automatic with fresh dense references across all supplied 2D families."""
import json,os,sys
from pathlib import Path
import numpy as np
root=Path(sys.argv[1]);here=Path(__file__).resolve().parent
golden=here/'regression/golden.py'
sys.argv=[str(golden),str(root),str(here/'unused.npz')]
namespace={'__file__':str(golden),'__name__':'fixture_definitions'}
exec(compile(golden.read_text().split('results = {}')[0],str(golden),'exec'),namespace)
S=namespace['S'];TWOD=namespace['TWOD'];ANG=namespace['ANG']
from ghost_backend.execution.options import automatic_options,execution_scope
from ghost_backend.twod.preparation import preparation_scope
from ghost_backend.execution.selection import select_backend
rows=[]
for name,(g,f) in TWOD.items():
    opts=dict(automatic_options(),assembly_threads=1,blas_threads=1)
    r=S.solve_monostatic_rcs_2d(g,[f],ANG,geometry_units='meters',execution_options=opts)
    a=np.array([complex(s['rcs_amp_real'],s['rcs_amp_imag']) for s in r['samples']])
    with np.load(here/'base-native.npz') as ref:b=ref[name+'/dense']
    assert a.shape==b.shape and np.all(np.isfinite(a))
    error=float(max(abs(a-b))/max(abs(b)))
    assert error<1e-9,(name,error)
    rows.append(dict(case=name,error=error,samples=len(a),backend=r['metadata'].get('linear_backend')))
g,f=TWOD['pec_circle']
args=dict(geometry_snapshot=g,frequencies_ghz=[f],elevations_deg=ANG,geometry_units='meters')
opts=dict(automatic_options(),factorization='dense',assembly_threads=1,blas_threads=1)
with preparation_scope():
    legacy=select_backend(args,opts)
    with execution_scope(automatic_options()):
        automatic=select_backend(args,opts)
        again=select_backend(args,opts)
    assert not legacy['automatic_policy'] and automatic['automatic_policy']
    assert not automatic.get('forecast_reused') and again['forecast_reused']
assert automatic['objective']=='memory_and_size'
(here/'automatic-field-results.json').write_text(json.dumps(dict(cases=rows,cache_isolation=True),indent=2)+'\n')
print('PASS',len(rows),'Automatic field families and forecast-cache isolation')
