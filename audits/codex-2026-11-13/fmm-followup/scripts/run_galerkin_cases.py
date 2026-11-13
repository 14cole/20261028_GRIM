import pathlib,psutil,time,json
from monitor_run import run
D=pathlib.Path(__file__).parent
while any(p.info['cmdline'] and p.info['cmdline'][:2]==['python',str(D/'run_angle_cases.py')] for p in psutil.process_iter(['cmdline'])):time.sleep(2)
for engine in ['native','cached']:
 for k,label in [([12.,0.],'real'),([12.,-.2],'loss')]:run(f'gal-small-{engine}-{label}','galerkin_case.py',dict(engine=engine,n=128,k=k))
for r in D.glob('gal-small-*.json'):
 if '-resources' in r.name:continue
 if not r.stat().st_size:raise RuntimeError('Empty Galerkin control output '+r.name)
 data=json.loads(r.read_text());assert all(v['relative_error']<1e-10 for v in data['results']),data
for engine in ['native','cached']:
 for n,ghz in [(4000,2),(16000,15)]:run(f'gal-large-{engine}-{n}-{ghz}','galerkin_case.py',dict(engine=engine,n=n,k=[2*3.141592653589793*ghz*1e9/299792458.,0],radius=3.048/1.2,operators=['S','W'],repeats=2),timeout=900)
for kind,n,k,star in [('PEC',64,3.,False),('PEC',128,3.,False),('TE',128,3.,False),('TM',128,3.,False),('TE',128,12.,True),('TM',128,12.,True),('TE',512,40.,True),('TM',512,40.,True)]:
 run(f'system-{kind}-{n}-{int(k)}','system_case.py',dict(engine='cached',kind=kind,n=n,k=k,star=star,incident_angles=[0.,47.,121.] if n<=128 else [0.],gmres_max_cycles=6),timeout=600)
