from run_followups import run
run('final-coated-refined-fixed-frequency-dense',dict(body='coated',n=4000,radius=100.,frequency_ghz=0.04768926290582116,mode='dense',angles=19))
for mode in ['dense','compressed']:
 run('final-frequency-sweep-'+mode,dict(body='coated',n=600,radius=.2,frequency_ghz=2.,mode=mode,angles=7,frequency_factors=[.98,1.,1.02],fixed_mesh=True,options={'dense_residual_storage':'disk'} if mode=='dense' else {}))
