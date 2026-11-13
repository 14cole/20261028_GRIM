from run_followups import run,D,NEW,OLD,SCRIPTS
import subprocess,os,numpy as np
from geometry_cases import build as geometry

def check(script,args,name,env=None):
 with (D/name).open('w') as f:
  r=subprocess.run(['python',str(script),*args],stdout=f,stderr=subprocess.STDOUT,env=env or dict(os.environ,PYTHONPATH=NEW+'/tools/GHOST',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
 print(name,r.returncode,flush=True)
check(SCRIPTS/'test_numerical_followups.py',[],'focused.log')
check(SCRIPTS/'claude_tests/regression/run_all.py',[],'claude-regressions.log',dict(os.environ,GHOST_AUDIT_ROOT=NEW,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
check(SCRIPTS/'previous_tests/test_regressions.py',[],'previous-regressions.log')
for body in ['diel','coated']:
 for radius in [.01,100.]:
  for mode in ['dense','compressed']:
   run(f'final-{body}-{radius}-{mode}',dict(body=body,n=2000,radius=radius,mode=mode,angles=19))
run('final-coat-disk',dict(body='coated',n=2000,radius=.01,mode='dense',angles=19,options={'dense_residual_storage':'disk'}))
for degree,body in [(2,'coated'),(3,'diel')]:
 for mode in ['dense','compressed']:
  run(f'final-p{degree}-{body}-{mode}',dict(body=body,n=600,radius=.01,mode=mode,angles=7,options={'basis_order':degree}))
for mode in ['dense','compressed']:
 run('final-fallback-'+mode,dict(body='diel',n=600,radius=.01,mode=mode,angles=7,fallback=True,force_tile=True))
run('final-workers',dict(body='diel',n=600,radius=.01,mode='compressed',angles=7,threads=2,force_tile=True,force_process_tiles=True))
for scale in [.01,1.,100.]:
 n=300;line=scale*np.column_stack((np.linspace(-.3,.3,n+1),np.zeros(n+1)))
 text='Title: scaled thin layer\nSegment: sheet 1\nproperties: 1 1 10 0 0\n'+'\n'.join('%.17g %.17g %.17g %.17g'%(*a,*b) for a,b in zip(line[:-1],line[1:]))+'\nIBCS_Resistances:\n10 thin_dielectric %.17g 1\nDielectrics:\n1 2.0 -0.02 1.0 0.0\n'%(scale*.0001)
 p=D/f'thin-{scale}.geo';p.write_text(text)
 for mode in ['dense','compressed']:
  run(f'final-thin-{scale}-{mode}',dict(body='custom',geo=str(p),f=2/scale,mode=mode,angles=7,threads=1))
for body in ['diel','coated']:
 for mode in ['dense','compressed']:
  run(f'final-certified-{body}-{mode}',dict(body=body,n=300,radius=.1,frequency_ghz=1.,mode=mode,angles=3,certified=True))
for name,spec in [('star',dict(shape='star',material='coated',length_m=2.,frequency_ghz=2.,inner_ratio=.98)),('cavity',dict(shape='cavity',material='pec',length_m=.5,frequency_ghz=2.))]:
 text,_=geometry(spec);p=D/(name+'.geo');p.write_text(text)
 for mode in ['dense','compressed']:
  run('final-'+name+'-'+mode,dict(body='custom',geo=str(p),f=2.,mode=mode,angles=7,certified=name=='cavity',options={'mesh_strategy':'adaptive'} if name=='cavity' else {}))
check(SCRIPTS/'previous_tests/test_parallel_requests.py',[NEW,str(D/'parallel-requests.json')],'parallel.log')
check(SCRIPTS/'previous_tests/test_planner_refresh.py',[NEW,str(D/'planner-refresh.json')],'planner.log')
