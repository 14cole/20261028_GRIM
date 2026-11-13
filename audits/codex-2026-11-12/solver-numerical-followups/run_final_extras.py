from run_followups import run,D,NEW,OLD,SCRIPTS
import subprocess,os
# Eight drawn primitives and wavelength-based sampling ensure the adaptive
# controller is actually eligible, unlike the fixed-count preliminary mesh.
import numpy as np
points=.25*np.array([[-1,-.3],[1,-.3],[1,-.04],[-.7,-.04],[-.7,.04],[1,.04],[1,.3],[-1,.3],[-1,-.3]])
points=points[::-1]
p=D/'adaptive-cavity-cw.geo';p.write_text('Title: adaptive cavity\nSegment: body 2\nproperties: 2 -20 0 0 0\n'+'\n'.join('%.17g %.17g %.17g %.17g'%(*a,*b) for a,b in zip(points[:-1],points[1:]))+'\nIBCS_Resistances:\nDielectrics:\n')
for mode in ['dense','compressed']:
 run('final-adaptive-cavity-cw-'+mode,dict(body='custom',geo=str(p),f=6.,mode=mode,angles=7,certified=True,options={'mesh_strategy':'adaptive'}))
# Larger nonlocal thin-layer system, including its compression/storage cost.
import numpy as np
line=np.column_stack((np.linspace(-.3,.3,1201),np.zeros(1201)))
text='Title: large thin-layer control\nSegment: sheet 1\nproperties: 1 1 10 0 0\n'+'\n'.join('%.17g %.17g %.17g %.17g'%(*a,*b) for a,b in zip(line[:-1],line[1:]))+'\nIBCS_Resistances:\n10 thin_dielectric 0.0001 1\nDielectrics:\n1 2.0 -0.02 1.0 0.0\n'
p=D/'thin-large.geo';p.write_text(text)
for root,label in [(OLD,'before'),(NEW,'after')]:
 run('holdout-thin-large-'+label,dict(body='custom',geo=str(p),f=2.,mode='compressed',angles=7,threads=1),root)
run('final-thin-large-dense',dict(body='custom',geo=str(p),f=2.,mode='dense',angles=7,threads=1))

for cap in [.85,1.]:
 run(f'final-auto-single-{cap}',dict(body='diel',n=2000,radius=.01,mode='automatic',angles=19,threads=1,options={'ram_budget_gib':cap,'compressed_storage_mib':0}))
# Third timing pair to expose variability; keep the first pair too.
for root,label in [(OLD,'before'),(NEW,'after')]:
 run('final-diel8k-'+label+'-2',dict(body='diel',n=4000,mode='compressed',angles=181,probe_profile=True),root)

with (D/'focused.log').open('w') as f:
 subprocess.run(['python',str(SCRIPTS/'test_numerical_followups.py')],stdout=f,stderr=subprocess.STDOUT,check=True,env=dict(os.environ,PYTHONPATH=NEW+'/tools/GHOST',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))

with (D/'final-physics-regressions.log').open('w') as f:
 subprocess.run(['python',str(SCRIPTS/'claude_tests/regression/test_baseline_physics.py')],stdout=f,stderr=subprocess.STDOUT,check=True,env=dict(os.environ,GHOST_AUDIT_ROOT=NEW,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
