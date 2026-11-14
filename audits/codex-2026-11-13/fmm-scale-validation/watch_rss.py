"""Optional process RSS safety monitor; any stop censors the benchmark.
Usage: python watch_rss.py PID LIMIT_GIB OUTPUT_JSON
It does not replace solver admission or a hard OS memory limit.
"""
import os,sys,time,json,signal,datetime
from pathlib import Path
pid=int(sys.argv[1]);limit=float(sys.argv[2]);output=Path(sys.argv[3]);proc=Path('/proc')/str(pid)
def identity():return (proc/'stat').read_text().rsplit(')',1)[1].split()[19]
assert b'compressed_control.py' in (proc/'cmdline').read_bytes()
initial=identity();record=dict(pid=pid,limit_gib=limit,started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),peak_observed_gib=0.,terminated=False,scope='RSS safety monitor; its start time defines coverage, full-run RSS comes from external .time.json')
try:
 while identity()==initial:
  status=(proc/'status').read_text().splitlines();rss=next((int(x.split()[1]) for x in status if x.startswith('VmRSS:')),0)/2**20
  record['peak_observed_gib']=max(record['peak_observed_gib'],rss)
  if rss>limit:
   record.update(terminated=True,reason='Research RSS safety threshold exceeded; no validated comparison may be claimed')
   output.write_text(json.dumps(record,indent=2));os.kill(pid,signal.SIGTERM);break
  time.sleep(.2)
except (FileNotFoundError,ProcessLookupError):pass
output.write_text(json.dumps(record,indent=2))
