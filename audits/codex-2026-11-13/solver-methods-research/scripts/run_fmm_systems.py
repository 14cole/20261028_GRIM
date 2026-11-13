import subprocess,os,json,pathlib,time
D=pathlib.Path(__file__).parent
for n,k,kind,star in [(64,3.,'PEC',False),(128,3.,'PEC',False),(64,3.,'TE',False),(64,3.,'TM',False),(128,3.,'TE',False),(128,3.,'TM',False),(128,12.,'TE',True),(128,12.,'TM',True),(256,20.,'PEC',True)]:
 name=f'fmm-system-{kind}-{n}-{k}';out=D/name;spec=dict(n=n,k=k,kind=kind,star=star,out=str(out));path=out.with_suffix('.json')
 # Name contains a decimal dot; append extension rather than replace suffix.
 path=pathlib.Path(str(out)+'.json')
 if path.exists() and path.stat().st_size:continue
 start=time.perf_counter()
 with path.open('w') as f:
  try:
   r=subprocess.run(['python',str(D/'fmm_system_solve.py'),json.dumps(spec)],stdout=f,stderr=subprocess.PIPE,text=True,timeout=360,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',LD_LIBRARY_PATH='/workspace/fmm-libraries/toolchain/usr/lib/x86_64-linux-gnu'))
   if r.stderr:pathlib.Path(str(out)+'.stderr').write_text(r.stderr)
  except subprocess.TimeoutExpired:path.write_text(json.dumps(dict(spec,error='timeout',seconds=time.perf_counter()-start)))
 print(name,round(time.perf_counter()-start,2),flush=True)
