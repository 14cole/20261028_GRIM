"""Run one case in a fresh process; record wall, peak RSS; optional RSS guard (GiB) that stops the child."""
import sys, json, time, resource, subprocess, threading
name, script, spec = sys.argv[1:4]; guard = float(sys.argv[4]) if len(sys.argv) > 4 else None; t = time.time(); seen = [0.0]; stopped = [False]
with open('results/%s.stdout' % name, 'w') as o, open('results/%s.stderr' % name, 'w') as e:
    p = subprocess.Popen([sys.executable, script, spec], stdout=o, stderr=e)
    def watch():
        while p.poll() is None:
            try:
                rss = int(open('/proc/%d/statm' % p.pid).read().split()[1])*4096/2**30; seen[0] = max(seen[0], rss)
                if guard and rss > guard: stopped[0] = True; p.kill()
            except Exception: pass
            time.sleep(0.25)
    threading.Thread(target=watch, daemon=True).start(); rc = p.wait()
r = resource.getrusage(resource.RUSAGE_CHILDREN)
json.dump(dict(rc=rc, wall_s=time.time()-t, peak_gib=r.ru_maxrss/2**20, cpu_s=r.ru_utime+r.ru_stime, stopped_by_guard=stopped[0], guard_gib=guard, sampled_peak_gib=seen[0]), open('results/%s.time' % name, 'w'))
if rc == 0 and __import__('os').path.getsize('results/%s.stdout' % name) > 0:
    import shutil; shutil.copy('results/%s.stdout' % name, 'results/%s.json' % name)
