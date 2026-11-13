from run_followups import run,NEW,OLD
for repeat in range(2):
 for root,label,extra in [(OLD,'before',{}),(NEW,'probe',{'coarse_initial':True,'probe_relaxation':True}),(NEW,'tight',{'tight_initial':True,'probe_relaxation':True})]:
  run(f'diel8k-{label}-{repeat}',dict(body='diel',n=4000,mode='compressed',angles=181,probe_profile=True,**extra),root)
