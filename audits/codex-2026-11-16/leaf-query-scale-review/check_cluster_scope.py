"""Check actual partition geometry for diagonal subtree queries (no assembly)."""
import os,sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST'))
from ghost_backend.compressed.hmatrix import ClusterTree
records=[]
for n in (1024,4096,9478,32768):
    theta=np.linspace(0,2*np.pi,n//2,endpoint=False)
    for kind in ('circle','star','elongated'):
        radius=(1+.2*np.cos(5*theta)) if kind=='star' else np.ones_like(theta)
        xy=np.c_[radius*np.cos(theta),radius*np.sin(theta)]
        if kind=='elongated':xy[:,0]*=12
        xy=np.tile(xy,(2,1));leaf=223 if n==9478 else 256;tree=ClusterTree(xy,np.zeros(n),leaf);far,near=tree.partition(1.)
        leaf_hits=fallback_hits=0;max_ratio=0.;queries=0;max_array_ratio=0.
        for a,b in zip(tree.start,tree.stop):
            side=int(b-a)
            if side>1024:continue
            queries+=1
            for row,partners in far.items():
                r0,r1=int(tree.start[row]),int(tree.stop[row]);height=r1-r0
                local_rows=max(0,min(b,r1)-max(a,r0))
                if not local_rows:continue
                local_cols=sum(max(0,min(b,tree.stop[p])-max(a,tree.start[p])) for p in partners)
                if not local_cols:continue
                assert a<=r0<r1<=b and height<=(side+1)//2,(kind,n,a,b,r0,r1)
                assert all(tree.stop[p]<=r0 or tree.start[p]>=r1 for p in partners)
                width=sum(int(tree.stop[p]-tree.start[p]) for p in partners)
                # Stored low-rank blocks must provide a storage gain.
                rank=(height*width-1)//(height+width)
                assert rank<height<=(side+1)//2
                array_bytes=16*(side*side+2*local_rows*local_cols+rank*(local_rows+local_cols))
                max_array_ratio=max(max_array_ratio,array_bytes/(16*side*side))
                assert array_bytes<=4*16*side*side
                max_ratio=max(max_ratio,rank/side)
                if side<=leaf:leaf_hits+=1
                else:fallback_hits+=1
        assert leaf_hits==0
        records.append(dict(unknowns=n,geometry=kind,leaf=leaf,queried_subtrees=queries,ordinary_leaf_far_contributions=leaf_hits,
            fallback_far_contributions=fallback_hits,max_contributing_rank_to_query_side=max_ratio,
            max_array_liveness_to_result=max_array_ratio))
Path(__file__).with_name('cluster-scope.json').write_text(json.dumps(records,indent=2));print(json.dumps(records,indent=2))
