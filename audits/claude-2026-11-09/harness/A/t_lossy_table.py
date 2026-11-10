from ref import *
import ghost_backend.twod.polynomial_quadrature as pq
from ghost_backend.twod.assembly.kernels import KernelTable, Rejected, DomainRejected
import time, warnings; warnings.simplefilter('ignore')
k0=2*np.pi*3e9/299792458.0
print("near-table acceptance (degree 12, as polynomial_quadrature._build_kernel_table builds it) vs degree 16 (far-path retry):")
acc12=acc16=tot=0
rows=[]
for eps in (4-0.01j,4-0.1j,4-1j,2.5-0.5j,10-5j,12-12j,1-10j,1-100j,1-1000j,30-0.3j,3-3j,7-0.7j,2-2j,16-1.6j,5-0.05j,9-9j):
    k=k0*np.sqrt(eps); k=complex(k.real,-abs(k.imag))
    for upper in (2.0**-6,2.0**-4,2.0**-2):
        tot+=1; r=[]
        for deg in (12,16):
            try: KernelTable(k,upper,degree=deg); r.append('ok')
            except DomainRejected as ex: r.append('domain')
            except Rejected as ex: r.append('REJ '+str(ex)[29:])
        acc12+=r[0]=='ok'; acc16+=r[1]=='ok'
        if r[0]!='ok': rows.append(f"  eps={eps} k={k:.1f} upper={upper}: deg12 {r[0]} | deg16 {r[1]}")
print("\n".join(rows[:14])); print(f"accepted deg12 {acc12}/{tot}, deg16 {acc16}/{tot}")
# cost of the fallback
k=k0*np.sqrt(4-1j); k=complex(k.real,-abs(k.imag))
d=np.random.RandomState(0).uniform(1e-4,0.05,(2000,400))
T16=KernelTable(k,2.0**-4,degree=16)
for label,tab in (('exact hankel2e fallback',None),('table deg16',T16)):
    best=1e9
    for _ in range(3):
        t=time.perf_counter(); g,dg=pq._kernels(k,d,True,tab); best=min(best,time.perf_counter()-t)
    print(f"{label}: {best*1e9/d.size:.0f} ns per distance (G and dG)")
print('what near batches get for this k:', pq._table_for_ends(k,np.zeros((1,2)),np.array([[0.01,0]]),np.array([[0.01,0.]]),np.array([[0.02,0.01]])))
