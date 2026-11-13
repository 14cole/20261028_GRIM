from pathlib import Path
D=Path(__file__).parent;p=D/'cached_fmm.py';s=p.read_text()
s=s.replace('gradients=False):','gradients=False, near_storage=True, partition_points=None, support_radius=0.):')
s=s.replace('self.gradients = bool(gradients)','self.gradients = bool(gradients)\n        self.near_storage=bool(near_storage)')
s=s.replace('np.floor((x - lo) / self.side[levels])','np.floor(((x if partition_points is None else np.asarray(partition_points)) - lo) / self.side[levels])')
s=s.replace('abs(k) * self.side[l] * math.sqrt(2.0)','abs(k) * (self.side[l] * math.sqrt(2.0) + 2*support_radius)')
a=s.index('        rows, cols = [], []');b=s.index('        seen=set()',a)
s=s[:a]+'''        neighbors=[]; counts=np.empty(n,dtype=np.int64)
        for t,(bi,bj) in enumerate(b):
            qs=[]
            for di in range(-separation,separation+1):
                for dj in range(-separation,separation+1):
                    q=index.get((int(bi)+di,int(bj)+dj))
                    if q is not None:qs.append(q)
            qs.sort();neighbors.append(np.array(qs,dtype=int))
            counts[ends[t]:ends[t+1]]=sum(ends[q+1]-ends[q] for q in qs)-1
        self.leaf_neighbors=neighbors
        self.near_pairs=int(counts.sum());self.near_mono=self.near_dip=None;self.near_grad=[]
        if near_storage:
            normals_sorted=self.nrm[order]
            number=4 if gradients else 2
            required=self.near_pairs*(16*number+4)+4*(n+1)
            if required>3*2**30:raise MemoryError('Research near-point budget exceeded: '+str(required))
            indptr=np.r_[0,np.cumsum(counts)].astype(np.int64 if self.near_pairs>=2**31 else np.int32)
            indices=np.empty(self.near_pairs,dtype=indptr.dtype);data=[np.empty(self.near_pairs,complex) for _ in range(number)]
            for t,qs in enumerate(neighbors):
                cc=np.concatenate([np.arange(ends[q],ends[q+1]) for q in qs]);step=max(1,min(64,131072//len(cc)))
                for first in range(ends[t],ends[t+1],step):
                    rr=np.arange(first,min(ends[t+1],first+step));mask=rr[:,None]!=cc[None,:];ri=np.broadcast_to(rr[:,None],mask.shape)[mask];ci=np.broadcast_to(cc[None,:],mask.shape)[mask];loi,hii=int(indptr[rr[0]]),int(indptr[rr[-1]+1]);indices[loi:hii]=ci
                    dv=xs[ri]-xs[ci];dist=np.linalg.norm(dv,axis=1);common=.25j*k*hankel1(1,k*dist)/dist
                    data[0][loi:hii]=.25j*hankel1(0,k*dist)
                    data[1][loi:hii]=common*np.einsum('ij,ij->i',dv,normals_sorted[ci])
                    if gradients:
                        data[2][loi:hii]=-common*dv[:,0];data[3][loi:hii]=-common*dv[:,1]
            matrices=[sparse.csr_matrix((v,indices,indptr),shape=(n,n),copy=False) for v in data]
            self.near_mono,self.near_dip=matrices[:2];self.near_grad=matrices[2:]
'''+s[b:]
s=s.replace('if a is not None:\n            out+=self.near_mono@a','if a is not None and self.near_storage:\n            out+=self.near_mono@a').replace('if d is not None:out+=self.near_dip@d','if d is not None and self.near_storage:out+=self.near_dip@d')
s=s.replace('        self.levels = levels','        # The forced two-level tree can have subwavelength leaves. A diagonal\n        # translation there is not reliably accurate. For these small electrical\n        # domains, make the 4x4 leaf grid entirely direct; allocation guards still\n        # apply. This is a bounded fallback, not an adaptive wideband FMM.\n        self.low_frequency_direct = levels == 2 and span < 4*leaf_wavelengths*wavelength\n        if self.low_frequency_direct:\n            separation = max(separation,3); self.separation = separation\n        self.levels = levels')
p.write_text(s)
