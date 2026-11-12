"""Research-only P1 dielectric workspace hypothesis from the prior handoff.

This is not a proven bound or a production replacement. Explicit tile 128 is
required; numerical kernels and all downstream gates are unchanged.
"""
import contextvars

def install():
    from ghost_backend.twod import solver as s,operators as ops
    from ghost_backend.twod.formulations.regions import mesh_near_pair_count
    from ghost_backend.execution import dense_memory as dm
    from ghost_backend.execution.options import option
    active=contextvars.ContextVar('stress_forecast_resources',default=None)
    resources0=s._dense_formulation_resources
    def resources(*args,**kw):
        r=resources0(*args,**kw)
        if r['formulation']=='single_dielectric':r['research_near_pairs']=mesh_near_pair_count(args[0])
        return r
    s._dense_formulation_resources=resources
    estimate0=s._estimate_memory_gb
    def estimate(*args,**kw):
        token=active.set(kw.get('dense_resources'))
        try:return estimate0(*args,**kw)
        finally:active.reset(token)
    s._estimate_memory_gb=estimate
    forecast0=dm.forecast
    def forecast(d,count,batch,assembly,solve,extra,eligible,submission=False):
        r=active.get()
        if eligible and not submission and r and r['formulation']=='single_dielectric' and r['basis_width']==2:
            assert option('assembly_tile',0)==128
            n,q,w=r['nodes'],r['research_near_pairs'],2
            tile=min(r['panels'],128);workers=ops.get_assembly_threads()
            far=workers*tile*tile*(3*(64*w*w+64)+(1024+64*w*w))
            near=256*min(ops._NEAR_BATCH_MAX_SAMPLES,q*256)
            assembly=16*d*d+64*1024**2+8192*n+128*q+min(16*1024**2,3*16*w*w*q)+max(far,near)
        return forecast0(d,count,batch,assembly,solve,extra,eligible,submission=submission)
    dm.forecast=forecast
