"""Batch-driver planning forecast (the numbers MemoryAwareDispatcher admits by) for one geometry, vs threads the planner assumes."""
import sys, os, json
sys.path.insert(0,'..'); os.environ['TMPDIR']=os.path.join(os.getcwd(),'tmp')
from lib import *
import ghost_backend.hpc.scheduler as H
from ghost_backend.execution.options import automatic_options, execution_scope
from ghost_backend.runs.batch import combine_channels, apply_batch_choices
os.makedirs('geo',exist_ok=True)
def write(a,name):
    p=os.path.abspath('geo/%s.geo'%name)
    open(p,'w').write("Title: c\nSegment: body 2\nproperties: 2 0 0 0 0\n%s\nIBCS_Resistances:\nDielectrics:\n"%circle_rows(a,256))
    return p
paths={write(0.5,'c05'):[6.0], write(1.0,'c10'):[12.0], write(1.2,'c12'):[12.0], write(2.0,'c20'):[12.0]}
opts=automatic_options()
with execution_scope(opts):
    b=H.predict_2d_resources_for_geometries(paths,['TM','TE'],'meters',100000,fine_factor=1.0,n_angles=181,safety=1.35,solver_method='auto',workers=1)
    for p,batch in b.items():
        for (f,pol),plan in batch.items():
            if pol!='TM': continue
            me=plan.get('memory_estimate') or {}
            print(os.path.basename(p),f,'nodes',plan['nodes'],'dofs',plan.get('base_system_dofs'),'peak_gb',round(plan['peak_gb'],3),
                  'cands',{k:round(v['peak_gb'],3) for k,v in plan.get('backend_candidates',{}).items()},
                  'worker_allow_GiB',round((me.get('retained_worker_allowance_bytes') or 0)/2**30,3),'model',me.get('model'),'storage_limit_GiB',round((me.get('storage_limit_bytes') or 0)/2**30,2),'keys',[k for k in plan if 'mem' in k or 'peak' in k])
