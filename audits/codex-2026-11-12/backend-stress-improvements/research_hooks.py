"""Audit-only experiments. Never imported by production modules.

Block balancing changes the condition diagnostic, not the system or gates.
Loss-span forecasting is a hypothesis, not a safe production memory bound.
"""
def balance_closed_blocks():
    import numpy as np
    from ghost_backend.twod.formulations import combined_regions as c
    c.condition_balance_blocks = lambda layout: np.asarray(sorted(offset for offset,_ in layout['dof_map'].values()),int)

def install_loss_span():
    import inspect,math
    from contextvars import ContextVar
    from ghost_backend.compressed import hmatrix as h,memory as m
    waves_context=ContextVar('research_waves',default=())
    def span(diameter):
        return max((abs(k.real)*min(diameter,math.log(1/h.TOLERANCE)/abs(k.imag))
            if k.imag else abs(k.real)*diameter for k in waves_context.get()),default=0.)
    source=inspect.getsource(h.forecast_storage)
    assert source.count('k*tree.diameter[')==2
    source=source.replace('k*tree.diameter[a]','research_span(tree.diameter[a])').replace('k*tree.diameter[c]','research_span(tree.diameter[c])')
    namespace=dict(vars(h),research_span=span)
    exec(compile(source,'<audit-only loss-span forecast>','exec'),namespace)
    replacement=namespace['forecast_storage']
    original=m.hmatrix_storage
    def storage(mesh,infos,*args,**kwargs):
        waves=[complex(k) for info in infos for k in (info.k_plus,info.k_minus) if k is not None]
        token=waves_context.set(waves)
        try:
            result=original(mesh,infos,*args,**kwargs)
            if result is not None:
                result['research_loss_span']=True
                result['rank_model_note']='UNVALIDATED audit-only cluster attenuation span hypothesis'
            return result
        finally:waves_context.reset(token)
    h.forecast_storage=replacement
    m.hmatrix_storage=storage

def install_scaled_lu():
    """Audit-only two-sided max-equilibrated LU with physical inverse actions.

    The Dense owner has already copied or spooled the original matrix before
    lu_factor is called. Residual evaluation still uses that original matrix.
    Also transform transpose/adjoint solves used by condition estimation.
    """
    import weakref
    import numpy as np
    import scipy.linalg as la
    from ghost_backend.linalg.workspace import equilibrated_scaling_and_norm_1
    factor0,solve0=la.lu_factor,la.lu_solve
    scales={};hits=[]
    def factor(a,overwrite_a=False,check_finite=True):
        a=np.asarray(a)
        if not overwrite_a:a=np.array(a,copy=True,order='F')
        row,col,_=equilibrated_scaling_and_norm_1(a)
        a/=row[:,None];a/=col[None,:]
        lu,piv=factor0(a,overwrite_a=True,check_finite=check_finite)
        key=id(lu)
        scales[key]=(weakref.ref(lu,lambda ref:scales.pop(key,None)),row,col)
        hits.append(dict(unknowns=len(a),row_min=float(row.min()),row_max=float(row.max()),column_min=float(col.min()),column_max=float(col.max())))
        return lu,piv
    def solve(lu_and_piv,b,trans=0,overwrite_b=False,check_finite=True):
        entry=scales.get(id(lu_and_piv[0]))
        if entry is None or entry[0]() is not lu_and_piv[0]:
            return solve0(lu_and_piv,b,trans=trans,overwrite_b=overwrite_b,check_finite=check_finite)
        _,row,col=entry;left,right=(row,col) if trans==0 else (col,row)
        b=np.asarray(b);shape=(slice(None),None) if b.ndim==2 else slice(None)
        rhs=b/left[shape]
        x=solve0(lu_and_piv,rhs,trans=trans,overwrite_b=True,check_finite=check_finite)
        x/=right[shape]
        return x
    la.lu_factor,la.lu_solve=factor,solve
    return hits
