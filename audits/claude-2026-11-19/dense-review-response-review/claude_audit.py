"""Reviewer instrumentation, independent of Codex's observations.py.
spec['hook']   : builder module to install first ('claude_builder' | 'corrected_builder')
spec['audit']  : trace NumPy allocations during every inverse build and compare
                 with what each construction guard declares.
Always records every HMatrixFactor.inverse call (phase, trans, columns, corrections).
spec['inverse_tolerance'] : research override of the initial inverse tolerance.
"""
import importlib,time,tracemalloc
from contextlib import contextmanager
import numpy as np
def install(spec):
    module=importlib.import_module(spec.get('hook','claude_builder'));module.install(spec)
    if spec.get('direct_gather'):
        import query_hook;query_hook.install(price_leaves=bool(spec.get('price_leaves')))
    global RECORD,memory
    RECORD=module.RECORD;memory=module.memory
    from ghost_backend.compressed.construction import Construction,array_bytes
    from ghost_backend.compressed.hmatrix_factor import HMatrixSystem,HMatrixFactor
    RECORD['inverse_calls']=[];RECORD['audit']=[]
    inverse0=HMatrixFactor.inverse
    def inverse(self,rhs,trans=0,*a,**k):
        depth=getattr(self,'_claude_depth',0);self._claude_depth=depth+1
        before=self.event['refinement_steps'];t=time.perf_counter()
        try:return inverse0(self,rhs,trans,*a,**k)
        finally:
            self._claude_depth=depth
            if not depth:RECORD['inverse_calls'].append(dict(phase=getattr(self,'_solve_phase','unknown'),trans=int(trans),
                columns=int(np.asarray(rhs).shape[1]) if np.asarray(rhs).ndim==2 else 1,corrections=int(self.event['refinement_steps']-before),
                seconds=time.perf_counter()-t,tolerance=float(getattr(self,'tolerance',float('nan')))))
    HMatrixFactor.inverse=inverse
    if 'inverse_tolerance' in spec:
        fresh0=HMatrixFactor._fresh_build
        def fresh(self):
            self.initial_preconditioner_tolerance=spec['inverse_tolerance'];return fresh0(self)
        HMatrixFactor._fresh_build=fresh
    if not spec.get('audit'):return
    state=dict(base=0,stack=[],build=None)
    init0=HMatrixSystem.__init__
    def init(self,*a,**k):
        started=not tracemalloc.is_tracing()
        if started:tracemalloc.start()
        state['base']=tracemalloc.get_traced_memory()[0];tracemalloc.reset_peak()
        build=dict(entries=0,shortfalls=0,max_shortfall_bytes=0,worst=None,by_label={},max_actual_bytes=0,max_accounted_bytes=0);state['build']=build
        try:init0(self,*a,**k)
        finally:
            build['final_retained_bytes']=int(getattr(self,'bytes',0));build['final_traced_bytes']=int(tracemalloc.get_traced_memory()[0]-state['base'])
            RECORD['audit'].append(build);state['build']=None
            if started:tracemalloc.stop()
    HMatrixSystem.__init__=init
    step0=Construction.step
    @contextmanager
    def step(self,label,additional,*live):
        build=state['build']
        if build is None:
            with step0(self,label,additional,*live):yield
            return
        accounted=int(self.owner.bytes+array_bytes(live)+int(additional))
        entry=tracemalloc.get_traced_memory()[0]-state['base'];tracemalloc.reset_peak();frame=dict(peak=entry);state['stack'].append(frame)
        try:
            with step0(self,label,additional,*live):yield
        finally:
            peak=max(frame['peak'],tracemalloc.get_traced_memory()[1]-state['base']);state['stack'].pop()
            if state['stack']:state['stack'][-1]['peak']=max(state['stack'][-1]['peak'],peak)
            tracemalloc.reset_peak()
            short=peak-accounted;build['entries']+=1
            build['max_actual_bytes']=max(build['max_actual_bytes'],int(peak));build['max_accounted_bytes']=max(build['max_accounted_bytes'],accounted)
            e=build['by_label'].setdefault(label,dict(entries=0,shortfalls_over_1MiB=0,max_shortfall_bytes=-2**62,max_growth_bytes=0,max_declared_additional=0))
            e['entries']+=1;e['max_shortfall_bytes']=max(e['max_shortfall_bytes'],int(short));e['max_growth_bytes']=max(e['max_growth_bytes'],int(peak-entry));e['max_declared_additional']=max(e['max_declared_additional'],int(additional))
            if short>2**20:
                e['shortfalls_over_1MiB']+=1;build['shortfalls']+=1
                if short>build['max_shortfall_bytes']:build['max_shortfall_bytes']=int(short);build['worst']=dict(label=label,accounted=accounted,actual=int(peak),entry=int(entry),additional=int(additional),live=int(array_bytes(live)),retained=int(self.owner.bytes))
    Construction.step=step
