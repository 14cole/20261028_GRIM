import pathlib,psutil,time,shutil
from monitor_run import run
D=pathlib.Path(__file__).parent
# Run after the entire original queue; preserve every initial result first.
names=['run_angle_cases.py','run_galerkin_cases.py','run_holdouts.py','run_extra_cases.py']
while any(p.info['cmdline'] and p.info['cmdline'][:2] in [['python',str(D/n)] for n in names] for p in psutil.process_iter(['cmdline'])):time.sleep(2)
I=D/'initial_low_frequency';I.mkdir(exist_ok=True);shutil.copy2(D/'cached_fmm_before_low_frequency_fallback.py',I/'cached_fmm.py')
for prefix in ['gal-small-cached-real','gal-small-cached-loss','system-PEC-64-3','system-PEC-128-3','system-TE-128-3','system-TM-128-3','system-TE-128-12','system-TM-128-12']:
 for f in list(D.glob(prefix+'*')):
  if f.is_file():shutil.move(str(f),I/f.name)
for k,label in [([12.,0.],'real'),([12.,-.2],'loss')]:run(f'gal-small-cached-{label}','galerkin_case.py',dict(engine='cached',n=128,k=k))
for kind,n,k,star in [('PEC',64,3.,False),('PEC',128,3.,False),('TE',128,3.,False),('TM',128,3.,False),('TE',128,12.,True),('TM',128,12.,True)]:
 run(f'system-{kind}-{n}-{int(k)}','system_case.py',dict(engine='cached',kind=kind,n=n,k=k,star=star,incident_angles=[0.,47.,121.],gmres_max_cycles=6),timeout=600)
