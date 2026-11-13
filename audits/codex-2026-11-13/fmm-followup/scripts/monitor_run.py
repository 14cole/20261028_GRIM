import subprocess,psutil,pathlib,time,json,os,signal
D=pathlib.Path(__file__).parent
def run(name,script,spec,timeout=900):
 out=D/name;dest=D/(name+'.json')
 if dest.exists() and dest.stat().st_size:return
 spec=dict(spec,out=str(out));start=time.monotonic();peak_rss=peak_pss=peak_uss=0;max_processes=0;trace=[];last_pss=0;missing=0
 with dest.open('w') as stdout,(D/(name+'.stderr')).open('w') as stderr:
  p=subprocess.Popen(['python',str(D/script),json.dumps(spec)],stdout=stdout,stderr=stderr,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',LD_LIBRARY_PATH='/workspace/fmm-libraries/toolchain/usr/lib/x86_64-linux-gnu'))
  root=psutil.Process(p.pid)
  while p.poll() is None:
   try:processes=[root,*root.children(recursive=True)]
   except psutil.Error:processes=[]
   now=time.monotonic();rss=pss=uss=0;full=now-last_pss>=.2
   for proc in processes:
    try:
     rss+=proc.memory_info().rss
     if full:
      m=proc.memory_full_info();pss+=m.pss;uss+=m.uss
    except (psutil.Error,AttributeError):missing+=1
   peak_rss=max(peak_rss,rss);max_processes=max(max_processes,len(processes))
   if full:peak_pss=max(peak_pss,pss);peak_uss=max(peak_uss,uss);trace.append([now-start,len(processes),rss,pss,uss]);last_pss=now
   if now-start>timeout:os.killpg(p.pid,signal.SIGTERM);p.wait();dest.write_text(json.dumps(dict(spec,error='timeout',seconds=now-start)));break
   time.sleep(.025)
 (D/(name+'-resources.json')).write_text(json.dumps(dict(elapsed=time.monotonic()-start,exit_code=p.returncode,peak_sum_rss_gib=peak_rss/2**30,peak_sum_pss_gib=peak_pss/2**30,peak_sum_uss_gib=peak_uss/2**30,max_processes=max_processes,missing_samples=missing,pss_sampling_seconds=.2,trace=trace),indent=2))
 print(name,round(time.monotonic()-start,2),p.returncode,flush=True)
