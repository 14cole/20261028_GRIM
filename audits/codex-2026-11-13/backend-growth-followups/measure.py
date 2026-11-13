"""Measure exactly one fresh child. Usage: measure.py results/label -- command ..."""
import json,resource,subprocess,sys,time
from pathlib import Path
if len(sys.argv)<4 or sys.argv[2]!='--':raise SystemExit(__doc__)
label=Path(sys.argv[1]);label.parent.mkdir(parents=True,exist_ok=True);start=time.perf_counter()
with open(str(label)+'.stdout','w') as out,open(str(label)+'.stderr','w') as err:
 rc=subprocess.run(sys.argv[3:],stdout=out,stderr=err).returncode
u=resource.getrusage(resource.RUSAGE_CHILDREN)
record=dict(rc=rc,wall_seconds=time.perf_counter()-start,peak_gib=u.ru_maxrss/(2**30 if sys.platform=='darwin' else 2**20),cpu_seconds=u.ru_utime+u.ru_stime,command=sys.argv[3:])
Path(str(label)+'.time.json').write_text(json.dumps(record,indent=2));print(json.dumps(record));raise SystemExit(rc)
