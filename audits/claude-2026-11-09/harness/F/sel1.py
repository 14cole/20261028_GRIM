"""Automatic (adaptive) backend selection vs size and RAM budget. Planning only."""
import sys, os, time, json
sys.path.insert(0,'..'); os.environ['TMPDIR']=os.path.join(os.getcwd(),'tmp')
from lib import *
from ghost_backend.execution.options import execution_scope, validate_options
from ghost_backend.execution.selection import select_backend
from ghost_backend.twod.preparation import preparation_scope
def sel(a,f,ram=None,na=181,threads='auto',mesh='global'):
    g=circle_geo(a,256,props='2 0 0 0 0')
    o=validate_options(dict(factorization='adaptive',mesh_strategy=mesh,assembly_threads=threads,blas_threads=threads,compressed_storage_mib=0,ram_budget_gib=ram))
    kw=dict(geometry_snapshot=g,frequencies_ghz=[f],elevations_deg=list(np.linspace(0,180,na)),geometry_units='meters',max_panels=100000)
    t=time.time()
    try:
        with execution_scope(o), preparation_scope():
            s=select_backend(kw,o)
    except MemoryError as e:
        return dict(a=a,f=f,ram=ram,error=str(e)[:160])
    c=s['candidates']
    return dict(a=a,f=f,ram=ram,N=s['meshes'][0]['unknowns'],sel=s['selected'],retry=s['retry_order'],budget=round(s['admission_budget_gib'],2),
        dense=(round(c['dense']['cost'],2),round(c['dense']['peak_gb'],3)),comp=(round(c['compressed']['cost'],2),round(c['compressed']['peak_gb'],3)),
        hm=c['compressed'].get('hmatrix',False),batch=s.get('angle_batch_size'),adj=bool(s.get('resource_adjustment')),plan_s=round(time.time()-t,2), reason=s['reason'][:60])
which=sys.argv[1]
if which=='size':
    for a,f in ((0.5,6),(1,6),(1,12),(1.55,12),(1.65,12),(1.9,12),(2.0,12),(3,12),(4,12)):
        print(json.dumps(sel(a,f)))
if which=='ram':
    for a,f in ((1,12),(2,12),(4,12)):
        for ram in (None,8,4,2,1.5,1,0.5):
            print(json.dumps(sel(a,f,ram)))
if which=='thr':
    for a,f in ((1,12),(2,12)):
        for th in (1,2,4):
            print(json.dumps(sel(a,f,None,threads=th)))
