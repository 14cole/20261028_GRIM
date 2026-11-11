"""Exercise paths omitted by the timing matrix; tracing is not a timing benchmark."""
import collections,json,math,os,sys,threading
from pathlib import Path
from unittest.mock import patch
ROOT=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(ROOT/'tools/GHOST'))
os.environ['GHOST_HMATRIX_MIN_UNKNOWNS']='1'
import numpy as np
from ghost_backend.geometry.io import parse_geometry,build_geometry_snapshot
from ghost_backend.twod import solver as S
from ghost_backend.compressed import hmatrix, runtime
from ghost_backend.execution.options import execution_scope
def circle(n=128,r=1.):
    t=-np.linspace(0,2*np.pi,n+1);points=[(r*np.cos(a),r*np.sin(a)) for a in t];points[-1]=points[0]
    return '\n'.join('%.15g %.15g %.15g %.15g'%(*points[i],*points[i+1]) for i in range(n))
def geom(kind,props,points,ibc='',diel=''):
    return build_geometry_snapshot(*parse_geometry(f'Title: probe\nSegment: b {kind}\nproperties: {props}\n{points}\nIBCS_Resistances:\n{ibc}\nDielectrics:\n{diel}\n'))
options=dict(factorization='compressed',assembly_threads=1,blas_threads=1)
records=[]
def run(name,fn,trace=False):
    calls=collections.Counter(); reasons=[]
    original=runtime.hierarchical
    def observed(*a,**kw):
        value,reason=original(*a,**kw)
        reasons.append(dict(oracle=type(a[0]).__name__,n=a[0].n,returned=type(value).__name__ if value is not None else None,reason=reason))
        return value,reason
    def profile(frame,event,arg):
        if event=='call':
            file=frame.f_code.co_filename
            prefix=str(ROOT/'tools/GHOST/ghost_backend')+'/'
            if file.startswith(prefix):calls[(file[len(prefix):],frame.f_code.co_name)]+=1
    if trace:sys.setprofile(profile);threading.setprofile(profile)
    try:
        with patch.object(runtime,'hierarchical',observed):
            r=fn()
        rec=dict(name=name,samples=len(r['samples']),backend=r['metadata'].get('linear_backend'),
            quality_passed=r['metadata'].get('quality_gate',{}).get('passed'),hierarchical_attempts=reasons,
            calls=[dict(file=f,function=n,count=c) for (f,n),c in sorted(calls.items())])
        assert len(r['samples'])>0
    finally:
        sys.setprofile(None);threading.setprofile(None)
    records.append(rec)
    print(name,'OK',rec['samples'],rec['backend'],reasons,flush=True)
g=geom(2,'2 1 0 0 0',circle(1200))
run('hmatrix_native_calls',lambda:S.solve_monostatic_rcs_2d_survey(g,[.3],[0.,45.,90.],geometry_units='meters',execution_options=options),True)
g=geom(1,'1 1 10 0 0',circle(128),ibc='10 thin_dielectric 0.0001 1',diel='1 2.0 -0.02 1.0 0.0')
run('ordinary_dielectric_thin_layer',lambda:S.solve_monostatic_rcs_2d_survey(g,[.03],[0.,45.,90.],geometry_units='meters',execution_options=options))
assert any(x['reason'] and 'inverse mass' in x['reason'] for x in records[-1]['hierarchical_attempts'])
g=geom(2,'2 1 0 0 0',circle(128))
with patch.object(hmatrix,'build_pair',side_effect=hmatrix.HMatrixRejected('injected measured-error rejection')),patch.object(hmatrix,'HMatrixOperator',side_effect=hmatrix.HMatrixRejected('injected measured-error rejection')):
    run('hmatrix_rejection_falls_back_to_tiles',lambda:S.solve_monostatic_rcs_2d_survey(g,[.03],[0.,45.,90.],geometry_units='meters',execution_options=options))
assert records[-1]['backend']=='cpu_compressed'
from ghost_backend.bor import dispatch as D
t=np.linspace(0,np.pi,41);points=[(.1*np.sin(a),.1*np.cos(a)) for a in t];points[0]=(0.,.1);points[-1]=(0.,-.1)
g=geom(2,'2 1 0 0 0','\n'.join('%.15g %.15g %.15g %.15g'%(*points[i],*points[i+1]) for i in range(40)))
with execution_scope({},limit_blas=True):
    run('bor_compressed_uses_tiles',lambda:D.solve_monostatic_rcs_bor_survey(g,[.3],[0.,45.,90.],geometry_units='meters',workers=1,bor_options=dict(factorization='compressed')),True)
assert any(x['file']=='compressed/operator.py' and x['function']=='__init__' for x in records[-1]['calls'])
Path(sys.argv[2]).write_text(json.dumps(records,indent=2)+'\n')
