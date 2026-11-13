from run_followups import run,D,NEW,OLD
from geometry_cases import build
# Fresh sequential controls after production source is frozen.
for repeat in range(2):
 for root,label in [(OLD,'before'),(NEW,'after')]:
  run(f'final-diel8k-{label}-{repeat}',dict(body='diel',n=4000,mode='compressed',angles=181,probe_profile=True),root)
for n in [3000,6000]:
 for root,label in [(OLD,'before'),(NEW,'after')]:
  run(f'holdout-diel{2*n}-{label}',dict(body='diel',n=n,mode='compressed',angles=19,probe_profile=True),root)
for root,label in [(OLD,'before'),(NEW,'after')]:
 run(f'holdout-airfoil3-{label}',dict(body='airfoil',f=3.,mode='compressed',angles=19),root)
# Irregular, lossless single dielectric: tests the initialization policy away
# from the lossy circles used for calibration.
text,_=build(dict(shape='star',material='diel',length_m=2.,frequency_ghz=2.,n=3000,eps=[4.,0.]))
p=D/'lossless-star.geo';p.write_text(text)
for root,label in [(OLD,'before'),(NEW,'after')]:
 run('holdout-lossless-star-'+label,dict(body='custom',geo=str(p),f=2.,mode='compressed',angles=19,probe_profile=True),root)
for mode in ['dense','compressed']:
 run('final-regional-workers-'+mode,dict(body='coated',n=600,radius=.01,mode=mode,angles=7,threads=2,force_tile=True,force_process_tiles=True))
run('final-random-rhs',dict(body='diel',n=600,radius=.01,mode='compressed',angles=3,random_rhs_checks=True))
for cap in [.85,1.]:
 run(f'final-auto-{cap}',dict(body='diel',n=2000,radius=.01,mode='automatic',angles=19,options={'ram_budget_gib':cap,'compressed_storage_mib':0}))
# Larger nonlocal thin-layer system, including its compression/storage cost.
import numpy as np
line=np.column_stack((np.linspace(-.3,.3,1201),np.zeros(1201)))
text='Title: large thin-layer control\nSegment: sheet 1\nproperties: 1 1 10 0 0\n'+'\n'.join('%.17g %.17g %.17g %.17g'%(*a,*b) for a,b in zip(line[:-1],line[1:]))+'\nIBCS_Resistances:\n10 thin_dielectric 0.0001 1\nDielectrics:\n1 2.0 -0.02 1.0 0.0\n'
p=D/'thin-large.geo';p.write_text(text)
for root,label in [(OLD,'before'),(NEW,'after')]:
 run('holdout-thin-large-'+label,dict(body='custom',geo=str(p),f=2.,mode='compressed',angles=7,threads=1),root)
run('final-thin-large-dense',dict(body='custom',geo=str(p),f=2.,mode='dense',angles=7,threads=1))
spec=dict(shape='star',material='coated',length_m=6.096,frequency_ghz=2.,inner_ratio=.99967)
text,description=build(spec);p=D/'thin-coated-20ft-star.geo';p.write_text(text)
run('final-20ft-star-dense',dict(body='custom',geo=str(p),f=2.,mode='dense',angles=7,options={'ram_budget_gib':8.,'dense_residual_storage':'disk'}))
