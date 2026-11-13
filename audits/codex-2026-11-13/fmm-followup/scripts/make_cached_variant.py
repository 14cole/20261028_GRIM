from pathlib import Path
D=Path(__file__).parent;s=(D/'claude_reference/fmm2d.py').read_text()
s=s.replace('class HelmholtzFMM:', 'class HelmholtzFMM:')
s=s.replace('max_leaf_points=None):','max_leaf_points=None, separation=1, tile_points=0, gradients=False):')
s=s.replace('self.k = k = float(k)', 'self.k = k = complex(k)\n        self.separation = separation = int(separation)\n        self.tile_points = int(tile_points)\n        self.gradients = bool(gradients)\n        if separation < 1 or k.real <= 0 or k.imag < 0: raise ValueError("Requires separation>=1 and passive H1 wavenumber")')
s=s.replace('2 * math.pi / k','2 * math.pi / abs(k)').replace('_truncation(k * self.side[l]', '_truncation(abs(k) * self.side[l]')
s=s.replace('for di in (-1, 0, 1):','for di in range(-separation,separation+1):').replace('for dj in (-1, 0, 1):','for dj in range(-separation,separation+1):').replace('max(abs(ox), abs(oy)) > 1:', 'max(abs(ox), abs(oy)) > separation:')
s=s.replace('self.shift_up = [None] * (levels + 1)', 'self.shift_up = [None] * (levels + 1)\n        self.shift_down = [None] * (levels + 1)')
s=s.replace('self.shift_up[l] = np.exp(-1j * k * (off @ self.s[l - 1].T))', 'self.shift_down[l] = np.exp(1j * k * (off @ self.s[l - 1].T))\n            self.shift_up[l] = np.exp(-1j * k * (off @ self.s[l - 1].T))')
s=s.replace('self.E = np.exp(-1j * phase)', 'self.Eout = np.exp(1j * phase)\n        self.E = np.exp(-1j * phase)')
s=s.replace('self.near_pairs = len(rows)', '''self.near_grad = []
        if gradients:
            scale = -0.25j*k*hankel1(1,k*r)/r
            self.near_grad = [sparse.csr_matrix((scale*dvec[:,j],(rows,cols)),shape=(n,n)) for j in range(2)]
        self.near_pairs = len(rows)''')
s=s.replace('def apply(self, mono=None, dip=None):', 'def apply(self, mono=None, dip=None, gradient=False):')
s=s.replace('ref = mono if mono is not None else dip', 'if gradient and (not self.gradients or dip is not None): raise ValueError("Gradient supports charge-only plans")\n        ref = mono if mono is not None else dip')
a=s.index('        w = 0\n');b=s.index('        # M2M upward',a)
s=s[:a]+'''        M = [None] * (levels + 1)
        M[levels] = np.empty((len(self.leaf_start),self.Q[levels],B),complex)
        starts=self.leaf_start; ends=np.append(starts,self.n); first=0
        while first<len(starts):
            last=len(starts) if not self.tile_points else max(first+1,int(np.searchsorted(starts,starts[first]+self.tile_points)))
            i,j=int(starts[first]),int(ends[last]);w=0
            if a is not None: w=self.E[i:j,:,None]*a[i:j,None,:]
            if d is not None: w=w+(self.E[i:j]*self.dip[i:j])[:,:,None]*d[i:j,None,:]
            M[levels][first:last]=np.add.reduceat(w,starts[first:last]-i,axis=0)
            first=last
        del w
'''+s[b:]
s=s.replace('np.conj(self.shift_up[l])', 'self.shift_down[l]')
a=s.index('        out = np.einsum');b=s.index('\n\ndef direct',a)
s=s[:a]+'''        out=np.empty((self.n,B),complex)
        grad=np.empty((self.n,2,B),complex) if gradient else None
        tile=self.tile_points or self.n
        for i in range(0,self.n,tile):
            j=min(self.n,i+tile);local=Lc[self.leaf_of_point[i:j]];E=self.Eout[i:j]
            out[i:j]=np.einsum('nq,nqb->nb',E,local)*(0.25j/self.Q[levels])
            if gradient:
                for component in range(2):
                    grad[i:j,component]=np.einsum('nq,nqb,q->nb',E,local,1j*self.k*self.s[levels][:,component])*(0.25j/self.Q[levels])
        if a is not None:
            out+=self.near_mono@a
            if gradient:
                for component in range(2):grad[:,component]+=self.near_grad[component]@a
        if d is not None:out+=self.near_dip@d
        result=np.empty_like(out);result[self.order]=out
        if gradient:
            g=np.empty_like(grad);g[self.order]=grad
            return (result[:,0],g[:,:,0]) if vector else (result,g)
        return result[:,0] if vector else result
'''+s[b:]
# Replace the original incomplete byte counter with deduplicated retained array accounting.
a=s.index('        self.bytes = ');b=s.index('\n    def apply',a)
s=s[:a]+'''        seen=set()
        def retained(value):
            if isinstance(value,np.ndarray):
                root=value
                while isinstance(root.base,np.ndarray):root=root.base
                if id(root) in seen:return 0
                seen.add(id(root));return root.nbytes
            if sparse.issparse(value):return sum(retained(a) for a in (value.data,value.indices,value.indptr))
            if isinstance(value,(tuple,list)):return sum(retained(a) for a in value)
            return 0
        self.bytes=sum(retained(v) for v in self.__dict__.values())
'''+s[b:]
s='''# Research derivative of Claude fmm2d.py at fe0a8eb785d6697b9b008e45798ab48eda311f43.
# Changes: configurable separation, passive complex k, target gradients,
# tiled source/target workspaces and more complete retained-array accounting.
# Not a production solver or accuracy certificate.
'''+s
(D/'cached_fmm.py').write_text(s)
