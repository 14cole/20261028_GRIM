"""Inject one tile rejection, then perform real solves through public workflows."""
import json,math,sys
from pathlib import Path
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(sys.argv[1])/'tools/GHOST'))
from ghost_backend.geometry.io import parse_geometry,build_geometry_snapshot
from ghost_backend.twod import solver as S
from ghost_backend.compressed.factor import CompressedFactor
from ghost_backend.compressed.hmatrix import minimum_unknowns,HMatrixRejected
from ghost_backend.linalg.hierarchical import HierarchicalRejected
from ghost_backend.execution.options import hmatrix_retry_requested,execution_scope
def geometry(n=1200,thin=False):
    t=-np.linspace(0,2*np.pi,n+1);p=[(np.cos(a),np.sin(a)) for a in t];p[-1]=p[0]
    xy='\n'.join('%.15g %.15g %.15g %.15g'%(*p[i],*p[i+1]) for i in range(n))
    h='Title: test\nSegment: b 1\nproperties: 1 1 10 0 0\n' if thin else 'Title: test\nSegment: b 2\nproperties: 2 1 0 0 0\n'
    tail='\nIBCS_Resistances:\n10 thin_dielectric 0.0001 1\nDielectrics:\n1 2.0 -0.02 1.0 0.0\n' if thin else '\nIBCS_Resistances:\nDielectrics:\n'
    return build_geometry_snapshot(*parse_geometry(h+xy+tail))
def main():
    output=Path(__file__).with_name('retry-workflows-results.json')
    records=json.loads(output.read_text()) if output.exists() and len(sys.argv)>2 else []
    original=CompressedFactor.__init__
    for kind in (sys.argv[2:] or ('survey','certified','adaptive','thin_excluded','hmatrix_rejection','repeat_rejection')):
        calls=[]; raised=[0]
        def constructor(self,*a,**kw):
            if type(self) is CompressedFactor or kind=='repeat_rejection':
                calls.append(dict(retry=hmatrix_retry_requested(),threshold=minimum_unknowns()))
                if raised[0]==0 or kind in ('repeat_rejection','thin_excluded'):
                    raised[0]+=1
                    exception=HMatrixRejected if kind=='hmatrix_rejection' else HierarchicalRejected
                    raise exception('injected tile rejection for workflow validation')
            return original(self,*a,**kw)
        opts=dict(factorization='compressed',mesh_strategy='adaptive' if kind=='adaptive' else 'global',assembly_threads=1,blas_threads=1)
        args=dict(geometry_snapshot=geometry(thin=kind=='thin_excluded'),frequencies_ghz=[.03 if kind=='thin_excluded' else .3],elevations_deg=[0.,45.,90.],geometry_units='meters',max_panels=20000,execution_options=opts)
        fn=S.solve_monostatic_rcs_2d_certified if kind in ('certified','adaptive') else S.solve_monostatic_rcs_2d_survey
        try:
            with patch.object(CompressedFactor,'__init__',constructor):r=fn(**args)
        except HierarchicalRejected as exc:
            assert kind in ('thin_excluded','hmatrix_rejection','repeat_rejection'),(kind,str(exc))
            assert raised[0]==(1 if kind=='hmatrix_rejection' else 2),(kind,calls)
            records.append(dict(case=kind,outcome='bounded rejection',calls=calls,error=type(exc).__name__))
        else:
            assert kind in ('survey','certified','adaptive'),kind
            m=r['metadata'];assert m['quality_gate']['passed'];assert 'compressed_hmatrix_retry' in m
            assert m['mesh_convergence_certified']==(kind!='survey')
            a=np.array([complex(x['rcs_amp_real'],x['rcs_amp_imag']) for x in r['samples']])
            args['execution_options']=dict(opts,factorization='dense');ref=fn(**args)
            b=np.array([complex(x['rcs_amp_real'],x['rcs_amp_imag']) for x in ref['samples']])
            error=float(max(abs(a-b))/max(abs(b)));assert error<1e-6,error
            records.append(dict(case=kind,outcome='passed',calls=calls,backend=m['linear_backend'],retry=m['compressed_hmatrix_retry'],certified=m['mesh_convergence_certified'],error=error,samples=len(a)))
        assert not hmatrix_retry_requested() and minimum_unknowns()==8192
        print(json.dumps(records[-1]),flush=True)
        output.write_text(json.dumps(records,indent=2)+'\n')
if __name__=='__main__':main()
