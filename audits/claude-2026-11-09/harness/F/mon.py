"""mon.py cmd... : run cmd, sample process tree at ~20 Hz: runnable (R-state) threads, RSS and PSS sums, process count. Prints MON json."""
import sys, os, time, json, subprocess, psutil, numpy as np
p=subprocess.Popen(sys.argv[1:]); me=psutil.Process(p.pid)
S=[]; t0=time.time(); k=0
def pss(pid):
    try:
        with open('/proc/%d/smaps_rollup'%pid) as f:
            for line in f:
                if line.startswith('Pss:'): return int(line.split()[1])*1024
    except OSError: return 0
    return 0
while p.poll() is None:
    try:
        procs=[me]+me.children(recursive=True)
    except Exception: break
    rss=run=nth=0; per=[]
    for q in procs:
        try:
            rss+=q.memory_info().rss; r=0
            for tid in os.listdir('/proc/%d/task'%q.pid):
                nth+=1
                try:
                    with open('/proc/%d/task/%s/stat'%(q.pid,tid)) as s: st=s.read().rsplit(')',1)[1].split()[0]
                    if st=='R': r+=1
                except OSError: pass
            run+=r; per.append(r)
        except Exception: pass
    ps=sum(pss(q.pid) for q in procs) if k%5==0 else None
    S.append((rss,run,nth,len(procs),ps,max(per) if per else 0)); k+=1
    time.sleep(0.05)
wall=time.time()-t0
ru=os.times()
run=np.array([s[1] for s in S]) if S else np.array([0])
print('MON '+json.dumps(dict(wall=round(wall,1), cpu_children_s=round(ru[2]+ru[3],1), peak_tree_rss_gib=round(max(s[0] for s in S)/2**30,3),
  peak_tree_pss_gib=round(max(s[4] or 0 for s in S)/2**30,3), max_procs=max(s[3] for s in S), max_threads=max(s[2] for s in S),
  runnable_mean=round(float(run.mean()),2), runnable_p50=int(np.percentile(run,50)), runnable_p90=int(np.percentile(run,90)), runnable_max=int(run.max()),
  frac_samples_over_4=round(float((run>4).mean()),3), max_runnable_one_proc=max(s[5] for s in S), nproc=os.cpu_count())))
