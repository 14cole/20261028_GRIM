"""Observe live correction charges and refinement per call without changing gates."""
import inspect,time
import numpy as np
def install_observations(spec,record):
    from ghost_backend.compressed.construction import Construction
    from ghost_backend.compressed.factor import CompressedFactor
    from ghost_backend.compressed.hmatrix_factor import HMatrixFactor
    record['live_correction_checks']=[];record['refinement_calls']=[]
    step0=Construction.step
    def step(self,label,additional,*live):
        if label in ('bounded research inverse packing','inverse child product (in place)','Woodbury correction'):
            frame=inspect.currentframe().f_back
            try:
                while frame is not None:
                    if frame.f_code.co_name=='build' and frame.f_code.co_filename.endswith(('claude_builder.py','corrected_builder.py')):
                        small=frame.f_locals.get('small')
                        if isinstance(small,np.ndarray):
                            record['live_correction_checks'].append(dict(label=label,bytes=small.nbytes,
                                explicitly_charged=any(x is small for x in live)))
                            break
                    frame=frame.f_back
            finally:del frame
        return step0(self,label,additional,*live)
    Construction.step=step
    refine0=CompressedFactor._refine
    def refine(self,b,trans):
        depth=getattr(self,'_research_refine_depth',0);self._research_refine_depth=depth+1
        before=self.event['refinement_steps'];start=time.perf_counter()
        try:return refine0(self,b,trans)
        finally:
            self._research_refine_depth=depth
            if not depth:record['refinement_calls'].append(dict(phase=getattr(self,'_solve_phase','unknown'),
                trans=trans,columns=b.shape[1],steps=self.event['refinement_steps']-before,
                tolerance=self.tolerance,seconds=time.perf_counter()-start))
    CompressedFactor._refine=refine
    if 'inverse_tolerance' in spec:
        fresh0=HMatrixFactor._fresh_build
        def fresh(self):
            self.initial_preconditioner_tolerance=spec['inverse_tolerance']
            return fresh0(self)
        HMatrixFactor._fresh_build=fresh
