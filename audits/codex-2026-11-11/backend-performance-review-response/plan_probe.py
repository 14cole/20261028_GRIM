import sys,json,math
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'tools/GHOST'))
import numpy as np
from ghost_backend.execution.options import automatic_options,execution_scope
from ghost_backend.execution.frequency_sweep import _plan
from ghost_backend.geometry.io import parse_geometry,build_geometry_snapshot
def arguments(n):
    t=-np.linspace(0,2*np.pi,n+1);p=[(np.cos(a),np.sin(a)) for a in t];p[-1]=p[0]
    rows='\n'.join('%.15g %.15g %.15g %.15g'%(*p[i],*p[i+1]) for i in range(n))
    g=build_geometry_snapshot(*parse_geometry('Title: probe\nSegment: b 2\nproperties: 2 1 0 0 0\n'+rows+'\nIBCS_Resistances:\nDielectrics:\n'))
    f=.314/(2*math.pi/n)*299792458/(2*math.pi)/1e9
    return dict(geometry_snapshot=g,frequencies_ghz=[.9*f,f],elevations_deg=[0.,45.,90.],geometry_units='meters',max_panels=100000)
if __name__=='__main__':
    records=[]
    for n in (4000,6000,8000):
        args=arguments(n)
        for budget in (2.,2.5,3.,3.5,4.):
            opts=dict(automatic_options(budget),mesh_strategy='global',assembly_threads='auto',blas_threads='auto')
            with execution_scope(opts,assembly_threads=4,memory_budget_gib=budget):
                r=_plan(args,opts,False,args['frequencies_ghz'],2,budget-1.,4)
            row=dict(n=n,budget=budget,modes=[x['selection']['selected'] for x in r],reservations=[x['memory_gib'] for x in r],fits=sum(x['memory_gib'] for x in r)<=budget-1. and len(r)==2)
            records.append(row);print(row,flush=True)
    Path(__file__).with_name('planning.json').write_text(json.dumps(records,indent=2)+'\n')
