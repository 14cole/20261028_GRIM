"""Balanced old/new/new/old timing order; run no regression jobs alongside it."""
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
manifest=json.loads((HERE/'snapshot_manifest.json').read_text())
for name,revision in [('ab_old_1','63429ba'),('ab_new_1','b233c19'),('ab_new_2','b233c19'),('ab_old_2','63429ba')]:
    subprocess.run([sys.executable,str(HERE/'study.py'),'--name',name,
        '--backend',manifest[revision]['backend']],check=True)
