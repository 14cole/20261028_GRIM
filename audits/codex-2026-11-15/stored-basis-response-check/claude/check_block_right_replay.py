"""Unit check: replay variant against v3 and a dense solve (duplicate + zero RHS)."""
import sys,numpy as np
sys.path.insert(0,sys.argv[1])
import block_gmres_right as v3, block_gmres_right_replay as vz
for seed,n,rb in [(0,70,20),(1,300,20),(2,300,6)]:
    r=np.random.default_rng(seed);A=np.eye(n)+0.3*(r.standard_normal((n,n))+1j*r.standard_normal((n,n)))/np.sqrt(n)
    P=np.linalg.inv(A+0.05*(r.standard_normal((n,n))+1j*r.standard_normal((n,n)))/np.sqrt(n))
    b=r.standard_normal((n,8))+1j*r.standard_normal((n,8));b[:,3]=b[:,1];b[:,5]=0
    ref=np.linalg.solve(A,b)
    for name,mod in [('v3',v3),('z',vz)]:
        x,d=mod.solve(lambda v:A@v,lambda v:P@v,b,restart_blocks=rb)
        print(seed,n,rb,name,'A',d['rhs_equivalent_matrix_applications'],'P',d['preconditioner_rhs_applications'],'cycles',d['cycles'],'err %.1e'%(np.linalg.norm(x-ref)/np.linalg.norm(ref)),'res %.1e'%d['max_scaled_relative_residual'])
        assert np.linalg.norm(x-ref)<=1e-10*np.linalg.norm(ref) and np.all(x[:,5]==0)
x,d=vz.solve(lambda v:v,lambda v:v,np.zeros((10,3)));assert not x.any();print('all-zero ok')
