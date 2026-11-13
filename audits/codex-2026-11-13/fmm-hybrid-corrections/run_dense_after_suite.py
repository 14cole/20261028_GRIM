import sys,time
from pathlib import Path
from run_investigation import run,HERE
for pid in map(int,sys.argv[1:]):
 while Path('/proc',str(pid)).exists():time.sleep(2)
assert 'SUITE COMPLETE' in (HERE/'results/suite.log').read_text()
run('dense_control.py','dense-4096-TE',dict(n=4096,k=80,pol='TE'))
run('preconditioned_solve.py','pre-1024-TE-detached',dict(n=1024,k=80,pol='TE',op_tol=.01,inv_tol=.01,dense_reference=True))
