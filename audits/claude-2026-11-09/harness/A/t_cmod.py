# Time the native far block with/without the unused H1 Horner evaluation (S/W-only passes).
from asm import *
import ctypes as ct, subprocess, shutil, re, time
src=open('/home/user/20261028_GRIM/tools/GHOST/ghost_backend/twod/assembly/native/far.c').read()
# variant: evaluate only the channels that are needed
mod=src.replace("static int kernel(const table_t *t, double r, int *hint, double *out) {","static int kernel(const table_t *t, double r, int *hint, double *out, int nch) {")
mod=mod.replace("    for (int c = 0; c < 2; ++c) {\n        int offset = 2 * c;\n        double re = base[4 * degree + offset]","    for (int c = 0; c < nch; ++c) {\n        int offset = 2 * c;\n        double re = base[4 * degree + offset]")
mod=mod.replace("if (kernel(&table, dist, &hint, value)) return 2;","if (kernel(&table, dist, &hint, value, want_k ? 2 : 1)) return 2;")
assert mod!=src and mod.count('nch')==3
open('far_mod.c','w').write(mod); open('far_orig.c','w').write(src)
for name in ('far_mod','far_orig'):
    subprocess.check_call(['cc','-O3','-std=c99','-ffp-contract=off','-shared','-fPIC',name+'.c','-o','lib'+name+'.so','-lm'])
from ghost_backend.twod.assembly.kernels import KernelTable
from ghost_backend.twod.assembly.native import far as nf
k=60.0; table=KernelTable(k,1.5)
rng=np.random.RandomState(0)
mb=nb=400; q=8
t,w=ops._get_quadrature(q); phi=np.column_stack((1-t,t))
def pts(n,x0):
    p0=np.column_stack((x0+np.arange(n)*0.003,np.zeros(n))); seg=np.tile([0.003,0.0],(n,1))
    return np.ascontiguousarray(p0[:,None,:]+t[None,:,None]*seg[:,None,:])
obs=pts(mb,0.0); srcp=pts(nb,0.02)   # all distances within table, mixed range
nrm=np.tile([0.0,1.0],(mb,1)); far=np.ones((mb,nb),np.uint8)
def call(lib,want_s,want_k,mir):
    fun=ct.CDLL('./'+lib).ghost_far_block
    p=ct.c_void_p
    fun.argtypes=[ct.c_int64,ct.c_int64,ct.c_int,ct.c_int]+[p]*7+[ct.c_int]*4+[ct.c_double]*2+[ct.c_int,p,ct.c_int,p,p,p,p]; fun.restype=ct.c_int
    accs=[np.zeros((4,mb,nb),complex) for _ in range(3)]
    best=1e9
    for rep in range(5):
        t0=time.perf_counter()
        st=fun(mb,nb,q,2,obs.ctypes.data,srcp.ctypes.data,w.ctypes.data,phi.ctypes.data,nrm.ctypes.data,nrm.ctypes.data,far.ctypes.data,
               1,want_s,want_k,mir,k,0.0,len(table.bounds)-1,table.bounds.ctypes.data,table.normalized_power.shape[1]-1,table.normalized_power.ctypes.data,
               accs[0].ctypes.data,accs[1].ctypes.data,accs[2].ctypes.data)
        best=min(best,time.perf_counter()-t0)
        assert st==0
    return best,accs[0].copy()
for label,(ws,wk,mir) in (('S only (W-only / TM-PEC pass)',(1,0,0)),('S+K+Kt',(1,1,1))):
    a,A=call('libfar_orig.so',ws,wk,mir); b,B=call('libfar_mod.so',ws,wk,mir)
    print(f"{label}: original {a*1e9/(mb*nb*q*q):.1f} ns/sample, skip-unused-H1 {b*1e9/(mb*nb*q*q):.1f} ns/sample, speedup {a/b:.2f}x, S bitwise equal {np.array_equal(A,B)}")
