import pathlib,psutil,time
from monitor_run import run
D=pathlib.Path(__file__).parent
waiting=['run_angle_cases.py','run_galerkin_cases.py','run_holdouts.py']
while any(p.info['cmdline'] and p.info['cmdline'][:2] in [['python',str(D/name)] for name in waiting] for p in psutil.process_iter(['cmdline'])):time.sleep(2)
run('nystrom-tight-star','nystrom_tight_case.py',dict(kind='star',k=160.,ppw=12),timeout=600)
run('nystrom-tight-circle','nystrom_tight_case.py',dict(kind='circle',k=20.,ppw=40),timeout=600)
