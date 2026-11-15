"""Reviewer microbenchmark, written before opening Codex's benchmark scripts.
Synthetic complex128 F-order matrix; residual-style product A@X for several
layouts of X and of the output. Alternating order, medians of 5."""
import os,sys,time,json,numpy as np
n=int(sys.argv[1]);threads=os.environ.get('OPENBLAS_NUM_THREADS')
r=np.random.default_rng(1);A=np.asfortranarray(r.standard_normal((n,n))+1j*r.standard_normal((n,n)))
out={}
for cols in (1,8,16,64,180,360):
    XF=np.asfortranarray(r.standard_normal((n,cols))+1j*r.standard_normal((n,cols)));XC=np.ascontiguousarray(XF)
    outF=np.empty((n,cols),complex,order='F');outC=np.empty((n,cols),complex,order='C')
    from scipy.linalg.blas import zgemm
    variants={
     'A@XF (default out)':lambda:A@XF,
     'A@XC (default out)':lambda:A@XC,
     'matmul(A,XF,out=F)':lambda:np.matmul(A,XF,out=outF),
     'matmul(A,XC,out=F)':lambda:np.matmul(A,XC,out=outF),
     'matmul(A,XF,out=C)':lambda:np.matmul(A,XF,out=outC),
     'zgemm(A,XF)':lambda:zgemm(1.,A,XF),
    }
    ref=zgemm(1.,A,XF);t={k:[] for k in variants};flags={};err={}
    names=list(variants)
    for rep in range(5):
        for k in (names if rep%2==0 else names[::-1]):
            s=time.perf_counter();y=variants[k]();t[k].append(time.perf_counter()-s)
            flags[k]='F' if y.flags.f_contiguous and not y.flags.c_contiguous else 'C' if y.flags.c_contiguous and not y.flags.f_contiguous else 'both'
            err[k]=float(np.linalg.norm(y-ref)/np.linalg.norm(ref))
    out[cols]={k:dict(median=float(np.median(v)),min=float(min(v)),max=float(max(v)),result_order=flags[k],rel_diff_vs_zgemm=err[k]) for k,v in t.items()}
    print(cols,{k:(round(v['median'],4),v['result_order'],'%.0e'%v['rel_diff_vs_zgemm']) for k,v in out[cols].items()},flush=True)
json.dump(dict(n=n,threads=threads,numpy=np.__version__,results=out),open(sys.argv[2],'w'),indent=1)
