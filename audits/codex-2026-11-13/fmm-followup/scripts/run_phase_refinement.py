import pathlib,psutil,time
from monitor_run import run
D=pathlib.Path(__file__).parent
while any(p.info['cmdline'] and p.info['cmdline'][:2]==['python',str(D/'run_unmonitored_large.py')] for p in psutil.process_iter(['cmdline'])):time.sleep(2)
for ppw in [20,80]:run(f'nystrom-tight-circle-ppw{ppw}','nystrom_tight_case.py',dict(kind='circle',k=20.,ppw=ppw),timeout=600)
