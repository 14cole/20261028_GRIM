from ref import *
import ghost_backend.twod.operators as ops
from ghost_backend.execution import cpu
import warnings, sys, functools; warnings.simplefilter('ignore')
print=functools.partial(print,flush=True)
def assembled(mesh,k,state):
    def run():
        S,Kp=ops._assemble_linear_operator_matrices(mesh,k,True)
        W=ops._assemble_linear_hypersingular_matrix(mesh,k)
        return np.array(S),np.array(Kp),np.array(W)
    if state:
        st=cpu.CPUState(kernel_only=True); st.reuse_operators=False
        with cpu._STATE.override(st):
            out=run()
        return out+(st.table_events,)
    return run()+(None,)
def refW(S,k,o,s):
    return -complex(k)**2*np.dot(o.normal,s.normal)*S+np.array([[1,-1],[-1,1]])*S.sum()/(o.length*s.length)
h=0.01
rng=np.random.RandomState(3)
print("far-pair block error vs kL (pair at centre ratio 3.0..3.3, random orientation); errors rel to max|S block|, K' abs/(L L')/max|K kernel| ")
for kL in (0.05,0.3,1.0,1.57,3.0,3.2,6.0,8.0,12.0,20.0):
  for kk in (kL/h, kL/h*(1-0.5j)/abs(1-0.5j)):
    worst=np.zeros(6)
    for trial in range(6):
        ang1,ang2,dirn=rng.uniform(0,2*np.pi,3); ratio=rng.uniform(3.0,3.3); lr=rng.choice([1.0,0.5,0.1])
        a=0.5*h*np.array([np.cos(ang1),np.sin(ang1)]); c=ratio*h*np.array([np.cos(dirn),np.sin(dirn)])
        b=0.5*lr*h*np.array([np.cos(ang2),np.sin(ang2)])
        mesh=mesh_from([(-a,a),(c-b,c+b)])
        o,s=mesh.elements
        R=ref_pair(o,s,kk)
        for si,state in enumerate((False,True)):
            S,Kp,W,ev=assembled(mesh,kk,state)
            eS=np.max(abs(S[:2,2:]-R[0]))/np.max(abs(R[0]))
            # kernel scale for K: |k H1(kr)|/4 * L L'
            from scipy.special import hankel2
            ksc=abs(0.25*kk*hankel2(1,kk*ratio*h))*o.length*s.length
            eK=np.max(abs(Kp[:2,2:]-R[1]))/ksc
            Wr=refW(R[0],kk,o,s); eW=np.max(abs(W[:2,2:]-Wr))/np.max(abs(Wr))
            worst[3*si:3*si+3]=np.maximum(worst[3*si:3*si+3],(eS,eK,eW))
    print(f"kL={kL:5.2f} k={kk:.1f}  numpy: S {worst[0]:.1e} K' {worst[1]:.1e} W {worst[2]:.1e} | table/native: S {worst[3]:.1e} K' {worst[4]:.1e} W {worst[5]:.1e}")
