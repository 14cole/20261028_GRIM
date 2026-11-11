"""Exercise actual spawned frequency workers and compare with sequential execution."""
import json,math,sys
from pathlib import Path
import numpy as np
root=Path(sys.argv[1]);sys.path.insert(0,str(root/'tools/GHOST'))
from ghost_backend.execution.fresh_sweep import run_fresh
from ghost_backend.execution.options import automatic_options,execution_scope
from ghost_backend.twod import solver as S
from ghost_backend.geometry.io import parse_geometry,build_geometry_snapshot
def main():
    t=-np.linspace(0,2*np.pi,129);p=[(.1*np.cos(a),.1*np.sin(a)) for a in t];p[-1]=p[0]
    rows='\n'.join('%.15g %.15g %.15g %.15g'%(*p[i],*p[i+1]) for i in range(128))
    g=build_geometry_snapshot(*parse_geometry('Title: sweep\nSegment: b 2\nproperties: 2 1 0 0 0\n'+rows+'\nIBCS_Resistances:\nDielectrics:\n'))
    args=dict(geometry_snapshot=g,frequencies_ghz=[.3,.6,.9],elevations_deg=[0.,37.,90.],geometry_units='meters',max_panels=10000)
    opts=dict(automatic_options(3.),mesh_strategy='global',assembly_threads=2,blas_threads='auto')
    records=[]
    for certified in (False,True):
        fn=S.solve_monostatic_rcs_2d_certified if certified else S.solve_monostatic_rcs_2d_survey
        fields=[]
        for workers in (1,2):
            with execution_scope(opts,assembly_threads=4,memory_budget_gib=6.):
                r=run_fresh(fn,args,opts,'double',certified,frequency_workers=workers)
            fields.append(np.array([complex(s['rcs_amp_real'],s['rcs_amp_imag']) for s in r['samples']]))
            mode=r['metadata']['frequency_execution']['mode']
            assert mode==('sequential' if workers==1 else 'parallel'),r['metadata']['frequency_execution']
            assert r['metadata']['mesh_convergence_certified']==certified
            records.append(dict(certified=certified,workers=workers,execution=r['metadata']['frequency_execution'],samples=len(r['samples'])))
        assert np.allclose(fields[0],fields[1],rtol=1e-10,atol=1e-12)
    Path(__file__).with_name('frequency-sweep-results.json').write_text(json.dumps(records,indent=2)+'\n')
    print('PASS: sequential/spawned sweeps; survey and certification; 3 frequencies each')
if __name__=='__main__':main()
