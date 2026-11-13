import pathlib,psutil,time
from monitor_run import run
D=pathlib.Path(__file__).parent
while any(p.info['cmdline'] and p.info['cmdline'][:2]==['python',str(D/'run_point_cases.py')] for p in psutil.process_iter(['cmdline'])):time.sleep(2)
for rep in range(2):
 for strategy,workers in [('batch',1),('threads',4)]:run(f'angle-small-{strategy}-{rep}','angle_case.py',dict(ka=320,angles=32,strategy=strategy,workers=workers,batch=8))
for strategy,workers in [('batch',1),('threads',4),('processes',4)]:run(f'angle-640-{strategy}','angle_case.py',dict(ka=640,angles=61,strategy=strategy,workers=workers,batch=8))
run('angle-1150-full-threads','angle_case.py',dict(ka=1150,angles=181,strategy='threads',workers=4,batch=8),timeout=1200)
