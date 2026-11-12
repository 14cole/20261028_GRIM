"""Factor-stage experiment on exact saved physical matrices; not a full solve."""
import gc,json,mmap,os,resource,sys,tempfile,threading,time,traceback
from pathlib import Path
import numpy as np,psutil,scipy.linalg as la
from threadpoolctl import threadpool_limits
from out_of_core_lu import DiskLU,FusedDiskLU
P=Path(__file__).resolve().parent;source=Path(sys.argv[1]);variant=sys.argv[2];out=Path(sys.argv[3]);root=Path(sys.argv[4]);sys.path.insert(0,str(root/'tools/GHOST'))
from experiment_hooks import ScaledMixed
from ghost_backend.linalg.refined_lu import RefinedLU
proc=psutil.Process();timeline=[];stop=threading.Event();started=time.perf_counter();io0=proc.io_counters()
def sample():
 while not stop.is_set():
  mem=proc.memory_info();stat={k:int(v) for k,v in (x.split() for x in Path('/sys/fs/cgroup/memory.stat').read_text().splitlines())}
  timeline.append([time.perf_counter()-started,mem.rss,stat.get('anon',0),stat.get('file',0)]);stop.wait(.02)
thread=threading.Thread(target=sample);thread.start();error=None;metrics=[];factor=None;info={}
try:
 with threadpool_limits(limits=4),tempfile.TemporaryDirectory(prefix='scratch-factor-'+out.name+'-',dir=str(P)) as d:
  a=np.load(source,mmap_mode='r');n=len(a);rng=np.random.default_rng(515);b=rng.normal(size=(n,19))+1j*rng.normal(size=(n,19))
  with open(source,'rb') as f:os.posix_fadvise(f.fileno(),0,0,os.POSIX_FADV_DONTNEED)
  t=time.perf_counter()
  if variant.startswith(('disk','fused')):
   factor=(FusedDiskLU if variant.startswith('fused') else DiskLU)(a,Path(d)/'factor.bin',int((variant[5:] if variant.startswith('fused') else variant[4:]).split('_')[0]));solve=factor.solve
   info.update(disk_factor_bytes=n*n*16,logical_read_bytes=factor.bytes_read,logical_write_bytes=factor.bytes_written,flushes=factor.flushes)
   if variant.endswith('_refined'):
    raw_solve=solve;refinement_events=[];info['refinement_events']=refinement_events
    def solve(rhs,trans=0):
     x=raw_solve(rhs,trans)
     for corrections in range(11):
      applied=np.zeros_like(rhs);rownorm=np.zeros(n)
      for j in range(0,n,128):
       z=min(n,j+128);block=np.array(a[:,j:z],copy=True)
       if trans==0:applied+=block@x[j:z];rownorm+=np.sum(abs(block),axis=1)
       else:
        applied[j:z]=(block.T if trans==1 else block.conj().T)@x
        rownorm[j:z]=np.sum(abs(block),axis=0)
       del block;a._mmap.madvise(mmap.MADV_DONTNEED)
      residual=rhs-applied;den=rownorm.max()*np.max(abs(x),axis=0)+np.max(abs(rhs),axis=0)
      error=float(np.max(np.max(abs(residual),axis=0)/den))
      if np.isfinite(error) and error<=3e-15:
       refinement_events.append(dict(trans=trans,corrections=corrections,backward_error=error));return x
      if corrections==10 or not np.isfinite(error):raise np.linalg.LinAlgError('Disk double refinement failed')
      x+=raw_solve(residual,trans)

  else:
   original=np.array(a,order='F');a._mmap.madvise(mmap.MADV_DONTNEED)
   if variant in ('dense','dense_refined'):
    factor=la.lu_factor(np.array(original,order='F'),overwrite_a=True,check_finite=False);solve=lambda rhs,trans=0:la.lu_solve(factor,rhs,trans=trans,check_finite=False)
    if variant=='dense_refined':
     refinement_events=[];info['refinement_events']=refinement_events
     norms=[max(float(np.max(np.sum(abs(v[i:i+64]),axis=1))) for i in range(0,n,64)) for v in (original,original.T)]
     def solve(rhs,trans=0):
      x=la.lu_solve(factor,rhs,trans=trans,check_finite=False)
      for corrections in range(11):
       applied=original@x if trans==0 else original.T@x if trans==1 else np.conj(original.T@np.conj(x))
       residual=rhs-applied;den=norms[bool(trans)]*np.max(abs(x),axis=0)+np.max(abs(rhs),axis=0)
       error=float(np.max(np.max(abs(residual),axis=0)/den))
       if np.isfinite(error) and error<=3e-15:
        refinement_events.append(dict(trans=trans,corrections=corrections,backward_error=error));return x
       if corrections==10 or not np.isfinite(error):raise np.linalg.LinAlgError('Double refinement failed')
       x+=la.lu_solve(factor,residual,trans=trans,check_finite=False)

   else:factor=(ScaledMixed if variant=='scaled_mixed' else RefinedLU)(original);solve=factor.solve
  info['factor_seconds_including_input_read']=time.perf_counter()-t
  for trans in (0,1,2):
   rhs=b if trans==0 else b[:,:2];t=time.perf_counter();x=solve(rhs,trans);solve_seconds=time.perf_counter()-t
   # Original coefficient residual, bounded column streaming for every mode.
   applied=np.zeros_like(rhs);rownorm=np.zeros(n)
   for j in range(0,n,128):
    z=min(n,j+128);block=np.array(a[:,j:z],copy=True)
    if trans==0:applied+=block@x[j:z];rownorm+=np.sum(abs(block),axis=1)
    else:
     applied[j:z]=(block.T if trans==1 else block.conj().T)@x
     rownorm[j:z]=np.sum(abs(block),axis=0)
    del block;a._mmap.madvise(mmap.MADV_DONTNEED)
   residual=applied-rhs;den=rownorm.max()*np.max(abs(x),axis=0)+np.max(abs(rhs),axis=0);back=float(np.max(np.max(abs(residual),axis=0)/den))
   assert np.isfinite(back) and back<=1e-12,(variant,trans,back)
   metrics.append(dict(trans=trans,rhs_columns=rhs.shape[1],solve_seconds=solve_seconds,backward_error=back))
   if trans==0:np.savez_compressed(str(out)+'.npz',solution=x)
  if isinstance(factor,DiskLU):factor.close()
except Exception as exc:error=type(exc).__name__+': '+str(exc);info['traceback']=traceback.format_exc()
finally:
 stop.set();thread.join()
io=proc.io_counters();result=dict(source=source.name,variant=variant,error=error,n=locals().get('n'),wall_seconds=time.perf_counter()-started,peak_rss_gib=max(x[1] for x in timeline)/2**30,peak_cgroup_anon_gib=max(x[2] for x in timeline)/2**30,peak_cgroup_file_gib=max(x[3] for x in timeline)/2**30,io_read_bytes=io.read_bytes-io0.read_bytes,io_write_bytes=io.write_bytes-io0.write_bytes,metrics=metrics,**info)
Path(str(out)+'.json').write_text(json.dumps(result,indent=2)+'\n');np.savez_compressed(str(out)+'.timeline.npz',timeline=np.array(timeline));print(json.dumps(result),flush=True)
