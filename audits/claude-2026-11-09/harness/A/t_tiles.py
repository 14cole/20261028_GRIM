from asm import *
from ghost_backend.twod.assembly.compact import CompactOperator
import warnings, functools; warnings.simplefilter('ignore')
print=functools.partial(print,flush=True)
mesh=circle_mesh(150,a=0.2,jitter=0.7,seed=2)
n=len(mesh.nodes)
for k in (40.0, 40-25j):
    for state in (0,1):
        ops._ASSEMBLY_TILE=0
        A=fused(mesh,k,bool(state))
        ops._ASSEMBLY_TILE=17
        B=fused(mesh,k,bool(state)); B3=fused(mesh,k,bool(state),threads=3)
        ops._NATIVE_FAR=False; C=fused(mesh,k,bool(state)); ops._NATIVE_FAR=True
        ops._ASSEMBLY_TILE=0
        print(f"k={k} state={state}: tile17 vs single tile:", {x:f"{np.max(abs(A[x]-B[x]))/np.max(abs(A[x])):.1e}" for x in 'SKDW'},
              'threads bitwise', all(np.array_equal(B[x],B3[x]) for x in 'SKDW'), 'native vs numpy far', {x:f"{np.max(abs(C[x]-B[x]))/np.max(abs(A[x])):.1e}" for x in 'SKDW'})
        # identities: S symmetric, W symmetric, D = K'^T
        print('    S-S^T',f"{np.max(abs(B['S']-B['S'].T))/np.max(abs(B['S'])):.1e}",'W-W^T',f"{np.max(abs(B['W']-B['W'].T))/np.max(abs(B['W'])):.1e}",'D-K^T',f"{np.max(abs(B['D']-B['K'].T))/np.max(abs(B['K'])):.1e}")
    # compact rectangular subsets + masks + obs coefficients
    rng=np.random.RandomState(1)
    rows=np.sort(rng.choice(n,37,replace=False)); cols=np.sort(rng.choice(n,53,replace=False))
    mask=rng.rand(len(mesh.elements))<0.6; coeff=rng.randn(len(mesh.elements))+1j*rng.randn(len(mesh.elements))
    ops._ASSEMBLY_TILE=17
    out=ops._assemble_multi(mesh,k,True,[mask,None],output_node_ids_many=[(rows,cols),(cols,rows)],
                            single_layer_observation_coefficients_many=[coeff,None])
    full_m=ops._assemble_multi(mesh,k,True,[mask],single_layer_observation_coefficients=coeff)
    ops._ASSEMBLY_TILE=0
    S0,K0=out[0]; S1,K1=out[1]
    print('    compact masked/weighted vs full:',f"{np.max(abs(S0.values-full_m[0][0][np.ix_(rows,cols)]))/np.max(abs(A['S'])):.1e}",
          f"{np.max(abs(K0.values-full_m[0][1][np.ix_(rows,cols)]))/np.max(abs(A['K'])):.1e}",
          'compact unmasked vs fused:',f"{np.max(abs(S1.values-A['S'][np.ix_(cols,rows)]))/np.max(abs(A['S'])):.1e}",f"{np.max(abs(K1.values-A['K'][np.ix_(cols,rows)]))/np.max(abs(A['K'])):.1e}")
    # weighted masked reference from unmasked blocks: S_c[i,j] = sum over obs elems coefficient ... check via per-element brute force
    Sref=np.zeros((n,n),complex)
    els=mesh.elements
    for i in rng.choice(len(els),6,replace=False):
        for j in np.flatnonzero(mask)[:40]:
            pass
