"""Small all-angle native/fallback comparisons; no production files changed."""
import contextlib,json,math,os,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(sys.argv[1]);sys.path.insert(0,str(ROOT/'tools/GHOST'))
import numpy as np
from ghost_backend.geometry.io import parse_geometry,build_geometry_snapshot
from ghost_backend.twod import solver as S
from ghost_backend.twod.assembly.native import far,near,table
from ghost_backend.execution.options import execution_scope
assert far._dll() is not None and near.available() and table.library() is not None
n=256;t=-np.linspace(0,2*np.pi,n+1);pts=[(.1*np.cos(a),.1*np.sin(a)) for a in t];pts[-1]=pts[0]
lines='\n'.join('%.15g %.15g %.15g %.15g'%(*pts[i],*pts[i+1]) for i in range(n))
g=build_geometry_snapshot(*parse_geometry('Title: fallback\nSegment: b 2\nproperties: 2 1 0 0 0\n'+lines+'\nIBCS_Resistances:\nDielectrics:\n'))
rows=[];values={}
for native in (True,False):
    for mode,backend,threshold in [('dense','dense','8192'),('tile','compressed','8192'),('hmatrix','compressed','1')]:
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ,{'GHOST_HMATRIX_MIN_UNKNOWNS':threshold}))
            if not native:
                for name in ('_dll','library','tile_library','scatter_library'):
                    stack.enter_context(patch.object(far,name,return_value=None))
                stack.enter_context(patch.object(near,'ENABLED',False))
                stack.enter_context(patch.object(table,'library',return_value=None))
            result=S.solve_monostatic_rcs_2d_survey(g,[1.],[float(a) for a in np.linspace(0,180,31)],geometry_units='meters',
                execution_options=dict(factorization=backend,assembly_threads=1,blas_threads=1))
        value=np.array([complex(s['rcs_amp_real'],s['rcs_amp_imag']) for s in result['samples']])
        key=('native' if native else 'fallback')+'-'+mode;values[key]=value
        assert np.all(np.isfinite(value))
        rows.append(dict(case=key,samples=len(value),backend=result['metadata']['linear_backend'],
            quality_passed=result['metadata']['quality_gate']['passed']))
reference=values['native-dense']
for row in rows:
    value=values[row['case']];row['relative_amplitude_error_vs_native_dense']=float(max(abs(value-reference))/max(abs(reference)))
    assert row['relative_amplitude_error_vs_native_dense']<1e-9
for mode in ('dense','tile','hmatrix'):
    a,b=values['native-'+mode],values['fallback-'+mode]
    print(mode,'native vs fallback relative error',max(abs(a-b))/max(abs(a)))
out=Path(__file__).resolve().parent
(out/'fallback-results.json').write_text(json.dumps(rows,indent=2)+'\n')
np.savez_compressed(out/'fallback-fields.npz',**values)
print('PASS: six solves, 62 complex amplitudes each')
