from asm import *
for N in (190,2000,6000):
    a=0.5; h=2*np.pi*a/N; kL=0.31
    th=-np.linspace(0,2*np.pi,N+1)[:-1]-np.pi/N; C=a*np.column_stack((np.cos(th),np.sin(th)))
    tile=ops._assembly_tile_size(N,16*(18+3+1)+56)
    used=0; ideal=0; dup=0; tot=0
    idx=np.arange(N)
    for i0 in range(0,N,tile):
        for j0 in range(i0,N,tile):
            ci=C[i0:i0+tile]; cj=C[j0:j0+tile]
            r=np.linalg.norm(ci[:,None]-cj[None],axis=2)/h
            sep=np.abs(idx[i0:i0+tile,None]-idx[None,j0:j0+tile]); sep=np.minimum(sep,N-sep)
            far=(r>=3)&(sep>1)
            if not far.any(): continue
            q=ops._graded_far_order(kL,r[far].min(),8,1,False)
            per=np.where(r<5,7,np.where(r<10,6,5))   # row kL<=0.5 of _FAR_ORDER_TABLE applied per pair
            used+=far.sum()*q*q
            if i0==j0:
                dup+=(far.sum()/2)*q*q; ideal+=(per[far]**2).sum()/2
            else: ideal+=(per[far]**2).sum()
            tot+=far.sum()
    print(f"N={N} tile={tile}: S/K' far kernel samples used {used:.3g}; with per-pair order and no diagonal-tile duplicates {ideal:.3g} -> {used/ideal:.2f}x; diagonal-tile duplicate share {dup/used:.1%}; W-mode (uniform 8, incl. dup) {tot*64:.3g} -> {tot*64/ideal:.2f}x vs per-pair S table")
