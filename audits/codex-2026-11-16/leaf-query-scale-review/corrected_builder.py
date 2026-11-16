"""Corrected research copy: conservative child scratch and explicit live correction.
See claude/claude_builder.py for the pinned original. Production is unchanged.
"""
"""Reviewer research hook: sequential inverse build with honest storage accounting.

Replaces HMatrixSystem.build in this process only. Options (spec keys):
  builder: 'production' (untouched build) | 'sequential'
  packing: 'none' | 'bounded' (Codex's convert(); with builder 'production' this
           is Codex's own post-build hook, for a matched control)
  leaf_scaling: bool (sequential only): equilibrate each leaf before its LU
Every array is charged at its current size. Accounted high-water is recorded.
"""
import numpy as np,scipy.linalg as la
from codex_hooks import convert,memory
from rank_guard import convert_factor
import codex_hooks
RECORD={'packing':[],'conversions':[],'accounting':{},'storage_rejections':[],'builds':0,'u_copies':0,'residual_products':[]}
def install(spec):
    from ghost_backend.compressed.hmatrix_factor import HMatrixSystem
    from ghost_backend.compressed.inverse import Node
    import ghost_backend.linalg.hierarchical as hf
    builder=spec.get('builder','production');packing=spec.get('packing','none');scaling=bool(spec.get('leaf_scaling'))
    acct=RECORD['accounting'];acct.update(high_water_bytes=0,high_water_with_check_bytes=0,final_bytes=[])
    reserve0=HMatrixSystem.reserve;check0=HMatrixSystem.check_storage
    def check_storage(self,count):
        acct['high_water_with_check_bytes']=max(acct['high_water_with_check_bytes'],self.bytes+int(count))
        try:return check0(self,count)
        except MemoryError:
            RECORD['storage_rejections'].append(dict(retained_bytes=int(self.bytes),additional_bytes=int(count),budget_bytes=int(self.budget)));raise
    def reserve(self,count):
        reserve0(self,count);acct['high_water_bytes']=max(acct['high_water_bytes'],self.bytes)
    HMatrixSystem.check_storage=check_storage;HMatrixSystem.reserve=reserve
    init0=HMatrixSystem.__init__
    def init(self,*a,**k):
        RECORD['builds']+=1
        try:init0(self,*a,**k)
        finally:acct['final_bytes'].append(int(getattr(self,'bytes',0)))
    HMatrixSystem.__init__=init
    if builder=='production':
        if packing=='bounded':
            codex_hooks.install(dict(packing='bounded'));RECORD['packing']=codex_hooks.RECORD['packing'];RECORD['conversions']=codex_hooks.RECORD['conversions']
        elif packing!='none':raise ValueError(packing)
        if scaling:raise ValueError('leaf scaling needs the sequential builder')
        return
    if builder!='sequential':raise ValueError(builder)
    class ScaledLeaf(Node):
        """Leaf storing LU of Dr*A*Dc. A^-1 = Dc (DrADc)^-1 Dr."""
        def solve_into(self,b,result,trans=0):
            dr,dc=self.dr[:,None],self.dc[:,None]
            if trans==0:result[...]=dc*la.lu_solve(self.lu,dr*b,check_finite=False)
            else:result[...]=dr*la.lu_solve(self.lu,dc*b,trans=trans,check_finite=False)
    def pack(self,node,key,*live):
        if packing!='bounded':return
        a=getattr(node,key)
        with self.construction.step('bounded research inverse packing',a.size*8+80*min(a.size,codex_hooks.CHUNK),*live):
            small,record=(convert_factor(a,key) if spec.get('rank_guard') else convert(a));delta=a.nbytes-small.nbytes;setattr(node,key,small);self.bytes-=delta
        RECORD['conversions'].append(dict(n=node.n,key=key,**record));RECORD['packing'].append(dict(n=node.n,key=key,saved_bytes=int(delta),accounted_bytes=int(self.bytes)))
    def solve_in_place(self,child,u,*live):
        # e = child^-1 u written over u; production solve_into allows aliasing.
        if not (u.dtype==np.complex128 and u.flags.writeable):
            RECORD['u_copies']+=1
            with self.construction.step('copy inverse child input',u.nbytes,*live):
                u=np.array(u,complex)
            live=(*live,u)
        with self.construction.step('inverse child product (in place)',8*u.nbytes+1024**2,*live):
            child.checkpoint() if hasattr(child,'checkpoint') else None
            child.solve_into(u,u)
        return u
    def build(self,oracle,ids):
        self.checkpoint()
        node=Node();node.n=len(ids);node.leaf=len(ids)<=self.leaf;node.checkpoint=self.checkpoint
        compressed=False
        if not node.leaf:
            mid=len(ids)//2;left,right=ids[:mid],ids[mid:]
            if len(ids)<=self.DENSE_FALLBACK_LIMIT:
                # Small nodes keep production order so a rejected compression can fall back to a dense leaf.
                before=self.bytes
                try:
                    node.u12,node.v12,_=self.compress_block(oracle,left,right);self.reserve(node.u12.nbytes+node.v12.nbytes)
                    node.u21,node.v21,_=self.compress_block(oracle,right,left);self.reserve(node.u21.nbytes+node.v21.nbytes)
                    compressed=True
                except hf.HierarchicalRejected:
                    self.dense_fallbacks+=1;self.largest_dense_fallback=max(self.largest_dense_fallback,len(ids))
                    node.leaf=True;self.bytes=before
                    for name in ('u12','u21','v12','v21'):
                        if hasattr(node,name):delattr(node,name)
        if node.leaf:
            raw_bytes=len(ids)**2*16
            self.check_storage(raw_bytes+8*len(ids)+(16*len(ids) if scaling else 0))
            with self.construction.step('leaf coefficients',2*raw_bytes):
                raw=oracle.get(ids,ids)
            self.leaves+=1
            if scaling:
                leaf=ScaledLeaf();leaf.n=node.n;leaf.leaf=True;leaf.checkpoint=self.checkpoint
                dr=np.abs(raw).max(axis=1);dr=1/np.where(dr>0,dr,1.);raw*=dr[:,None]
                dc=np.abs(raw).max(axis=0);dc=1/np.where(dc>0,dc,1.);raw*=dc[None,:]
                leaf.dr,leaf.dc=dr,dc;self.reserve(dr.nbytes+dc.nbytes);leaf.lu=self.factor(raw);return leaf
            node.lu=self.factor(raw);return node
        node.left,node.right=self.build(oracle,left),self.build(oracle,right)
        if not compressed:
            node.u12,node.v12,_=self.compress_block(oracle,left,right);self.reserve(node.u12.nbytes+node.v12.nbytes)
        # e1 overwrites u12 (same shape and charge).
        node.e1=solve_in_place(self,node.left,node.u12);del node.u12
        if not compressed:
            node.u21,node.v21,_=self.compress_block(oracle,right,left);self.reserve(node.u21.nbytes+node.v21.nbytes)
        r,s=node.e1.shape[1],node.u21.shape[1];self.ranks.extend((r,s))
        self.check_storage(16*(r+s)**2+8*(r+s))
        with self.construction.step('Woodbury correction',16*((r+s)**2+2*r*s)):
            small=np.eye(r+s,dtype=complex)
            small[r:,:r]=node.v21 @ node.e1          # needs double v21, e1
        pack(self,node,'e1',small);pack(self,node,'v21',small)
        node.e2=solve_in_place(self,node.right,node.u21,small);del node.u21
        with self.construction.step('Woodbury correction',16*2*r*s,small):
            small[:r,r:]=node.v12 @ node.e2          # needs double v12, e2
        pack(self,node,'v12',small);pack(self,node,'e2',small)
        node.lu=self.factor(small) if r+s else None
        return node
    HMatrixSystem.build=build
