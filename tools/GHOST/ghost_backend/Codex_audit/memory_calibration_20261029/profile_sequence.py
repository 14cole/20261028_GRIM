"""Start worker calibration only after the serial revision comparison completes."""
import json
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
deadline=time.monotonic()+900
while not (HERE/'runs/ab_old_2/monitor.json').exists():
    if time.monotonic()>deadline:raise RuntimeError('Revision comparison did not finish')
    time.sleep(1)
assert json.loads((HERE/'runs/ab_old_2/monitor.json').read_text())['returncode']==0
backend=json.loads((HERE/'snapshot_manifest.json').read_text())['b233c19']['backend']
for name,case,threads,cap,release in [
    ('release_4','inlet15',4,6.,True),
    ('profile_2','inlet15',2,6.,False),
    ('profile_narrow_8','narrow15',8,8.,False)]:
    command=[sys.executable,str(HERE/'study.py'),'--name',name,'--backend',backend,
        '--case',case,'--threads',str(threads),'--cap',str(cap)]
    if release:command.append('--release-idle')
    subprocess.run(command,check=True)
