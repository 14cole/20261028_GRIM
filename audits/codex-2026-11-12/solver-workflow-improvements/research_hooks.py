"""Audit-only instrumentation and rejected/experimental parallelism; never imported by production."""
import contextvars, functools, threading,time
import numpy as np

def install(spec):
    evidence={'timers':{},'probes':[]}
    if spec.get('profile_geometry'):
        from ghost_backend.compressed import hmatrix as h
        from ghost_backend.twod.assembly.geometry_plan import AssemblyGeometry
        from ghost_backend.twod import solver as s
        lock=threading.Lock()
        def wrap(owner,name,label):
            original=getattr(owner,name)
            @functools.wraps(original)
            def call(*a,**kw):
                start=time.perf_counter()
                try:return original(*a,**kw)
                finally:
                    elapsed=time.perf_counter()-start
                    with lock:
                        row=evidence['timers'].setdefault(label,{'calls':0,'elapsed_sum':0.})
                        row['calls']+=1;row['elapsed_sum']+=elapsed
            setattr(owner,name,call)
        wrap(AssemblyGeometry,'__init__','AssemblyGeometry')
        wrap(h.ClusterTree,'__init__','ClusterTree')
        wrap(h.ClusterTree,'partition','ClusterTree.partition')
        wrap(s,'_allocation_rss_bytes','allocation_process_scan')
        from ghost_backend.execution.metrics import SolveMetrics
        wrap(SolveMetrics,'_sample_process_tree','telemetry_process_tree')
        wrap(s,'_build_panels','panels')
        wrap(s,'_build_linear_mesh_interface_aware','mesh')
    if spec.get('coarse_blas'):
        from ghost_backend.linalg import hierarchical as hf
        from threadpoolctl import threadpool_limits
        original=hf.compress_sampled
        def coarse(block,*a,**kw):
            if min(block.shape)>=1024:
                with threadpool_limits(limits=4,user_api='blas'):return original(block,*a,**kw)
            return original(block,*a,**kw)
        hf.compress_sampled=coarse
    if spec.get('parallel_solve'):
        from ghost_backend.compressed.hmatrix_factor import HMatrixSystem
        import scipy.linalg as la
        from concurrent.futures import ThreadPoolExecutor
        original=HMatrixSystem.__init__
        def initialize(self,*a,**kw):
            original(self,*a,**kw)
            root=self.root
            if root.leaf:return
            def solve_into(b,result,trans=0):
                root.checkpoint();n=root.left.n
                def children(first,second):
                    # Experiment: one coarse fork, join even on failure. Children
                    # keep serial recursion. Executor per call is intentionally
                    # charged in the measured complete solve.
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        job=pool.submit(contextvars.copy_context().run,root.left.solve_into,first,result[:n],trans)
                        root.right.solve_into(second,result[n:],trans)
                        job.result()
                if root.lu is None:children(b[:n],b[n:]);return
                if trans==0:
                    children(b[:n],b[n:]);z1,z2=result[:n],result[n:]
                    small=np.vstack((root.v12@z2,root.v21@z1))
                    correction=la.lu_solve(root.lu,small,check_finite=False);r=root.e1.shape[1]
                    z1-=root.e1@correction[:r];z2-=root.e2@correction[r:];return
                adj=lambda a:a.T if trans==1 else a.conj().T
                small=np.vstack((adj(root.e1)@b[:n],adj(root.e2)@b[n:]))
                correction=la.lu_solve(root.lu,small,trans=trans,check_finite=False);r=root.e1.shape[1]
                result[:n]=b[:n]-adj(root.v21)@correction[r:]
                result[n:]=b[n:]-adj(root.v12)@correction[:r]
                children(result[:n],result[n:])
            root.solve_into=solve_into
        HMatrixSystem.__init__=initialize
    if spec.get('compression_only'):
        from ghost_backend.compressed.factor import CompressedFactor
        from ghost_backend.compressed.hmatrix_factor import HMatrixFactor
        HMatrixFactor._backward_errors=CompressedFactor._backward_errors
        def physical_samples(self,x,b):
            residual,_=self.a.sample_residual(x,b)
            denominator=np.maximum(self.a.operator_norm*np.max(abs(x),axis=0)+np.max(abs(b),axis=0),1e-300)
            return np.max(abs(residual),axis=0)/denominator
        HMatrixFactor.sampled_errors=physical_samples
    if spec.get('tile_extra_refinement'):
        from ghost_backend.compressed.factor import CompressedFactor
        original_refine=CompressedFactor._refine
        def refine(self,b,trans):
            x,residual=original_refine(self,b,trans)
            for _ in range(3):
                self.checkpoint()
                x-=self.factor.apply(self.a.matmul(x,trans)-b,solve=True,trans=trans)
            return x,self.a.matmul(x,trans)-b
        CompressedFactor._refine=refine
    if spec.get('dense_extra_refinement'):
        from ghost_backend.linalg.dense import DenseFactor
        original_inverse=DenseFactor._apply_inverse
        def refined(self,b,return_residual=False):
            x=original_inverse(self,b)
            for _ in range(3):
                self.checkpoint()
                x+=original_inverse(self,b-self.a@x)
            return (x,b-self.a@x) if return_residual else x
        DenseFactor._apply_inverse=refined
    if spec.get('random_rhs_checks'):
        from ghost_backend.compressed.hmatrix_factor import HMatrixFactor
        original=HMatrixFactor.__init__
        def initialize(self,*a,**kw):
            original(self,*a,**kw)
            n=self.a.n;matrix=np.empty((n,n),complex)
            ids=np.arange(n)
            for start in range(0,n,64):
                matrix[start:start+64]=self.a.oracle.get(ids[start:start+64],ids)
            rng=np.random.default_rng(431)
            for trans in (0,1,2):
                op=matrix if trans==0 else matrix.T if trans==1 else matrix.conj().T
                cols=(self.a.compression_columns if trans==0 else self.a.compression_rows)[self.a.position]
                truth=(rng.standard_normal((n,3))+1j*rng.standard_normal((n,3)))*cols[:,None]
                b=op@truth;x=self.inverse(b,trans=trans)
                error=np.max(abs(x-truth)/cols[:,None])/np.max(abs(truth)/cols[:,None])
                backward=np.max(abs(op@x-b))/(np.linalg.norm(op,np.inf)*np.max(abs(x))+np.max(abs(b)))
                evidence['probes'].append(dict(polarization=getattr(self.a.oracle,'pol',None),trans=trans,forward_dimensionless=float(error),backward=float(backward)))
                if error>1e-8 or backward>1e-12:raise AssertionError(evidence['probes'][-1])
        HMatrixFactor.__init__=initialize
    return evidence
