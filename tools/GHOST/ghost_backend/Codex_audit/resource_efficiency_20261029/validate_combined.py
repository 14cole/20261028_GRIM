"""Run affected regressions only after all serial timing/capacity trials finish."""
import json,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
final=HERE/'runs/dogleg_magnetic15/monitor.json'
deadline=time.monotonic()+3600
while not final.exists():
    if time.monotonic()>deadline:raise RuntimeError('Numerical studies did not finish')
    time.sleep(1)
subprocess.run([sys.executable,str(HERE/'validate.py'),*json.loads((HERE/'combined_test_files.json').read_text())],check=True)
