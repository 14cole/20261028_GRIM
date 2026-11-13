"""Run one case in a fresh process; record wall time and whole-process peak RSS (through validation and output)."""
import sys, json, time, resource, subprocess
name, script, spec = sys.argv[1:4]; t = time.time()
with open('results/%s.json' % name, 'w') as o, open('results/%s.stderr' % name, 'w') as e:
    rc = subprocess.run([sys.executable, script, spec], stdout=o, stderr=e, timeout=7200).returncode
r = resource.getrusage(resource.RUSAGE_CHILDREN)
json.dump(dict(rc=rc, wall_s=time.time()-t, peak_gib=r.ru_maxrss/2**20, cpu_s=r.ru_utime+r.ru_stime), open('results/%s.time' % name, 'w'))

