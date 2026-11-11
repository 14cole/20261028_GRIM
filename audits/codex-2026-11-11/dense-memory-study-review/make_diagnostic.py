from pathlib import Path
p=Path(__file__).parent
s=(p/'profile_independent.py').read_text()
insert='''# Study-only experiment. Production files are never edited.
if spec.get('forecast_probe'):
    import inspect
    source=inspect.getsource(S._estimate_memory_gb)
    assert source.count('solve = 2*matrix +')==1
    if spec.get('lean_forecast'):
        assert spec.get('storage')=='disk' and spec.get('mode','dense')=='dense'
        # Retain every existing workspace/cache/assembly allowance; discount
        # exactly one coefficient matrix and add two residual read buffers.
        source=source.replace('solve = 2*matrix +',
            'solve = matrix + 2*16*d*min(d,max(256,(16*1024**2)//(16*d))) +')
    old='    return (max(assembly, solve) + extra + count*4096 + retained_worker_bytes()) / 1024**3'
    assert old in source
    source=source.replace(old,"    _study_forecasts.append(dict(n=n,d=d,matrix=matrix,assembly=assembly,solve=solve,extra=extra,batch=batch,formulation=kind))\\n"+old)
    S._study_forecasts=[]
    exec(compile(source,'<study-only-dense-forecast>','exec'),S.__dict__)
projection_requests=[]
from ghost_backend.compressed.hmatrix_factor import _RangeBlock
projection_workspace=_RangeBlock.product_workspace
def observe_projection(self,width,adjoint=False):
    count=projection_workspace(self,width,adjoint)
    if adjoint and count>256*1024**2:
        row=dict(shape=self.shape,width=width,workspace_bytes=count,
            complete_projection_bytes=16*self.shape[1]*width)
        if not projection_requests or projection_requests[-1]!=row:projection_requests.append(row)
    return count
_RangeBlock.product_workspace=observe_projection
if spec.get('chunk_projection'):
    # Causal experiment only: bounded columns, same original products/gates.
    from ghost_backend.compressed.hmatrix_factor import _RangeBlock
    project_original=_RangeBlock.project
    workspace_original=_RangeBlock.product_workspace
    chunk_columns=64
    def project_bounded(self,basis):
        width=basis.shape[1]
        if width<=chunk_columns:return project_original(self,basis)
        result=np.empty((width,self.shape[1]),dtype=np.complex128)
        for start in range(0,width,chunk_columns):
            self.checkpoint();stop=min(width,start+chunk_columns)
            result[start:stop]=project_original(self,basis[:,start:stop])
        return result
    def workspace_bounded(self,width,adjoint=False):
        return workspace_original(self,min(width,chunk_columns) if adjoint else width,adjoint)
    _RangeBlock.project=project_bounded
    _RangeBlock.product_workspace=workspace_bounded
if spec.get('trace_allocations'):
    import tracemalloc
    tracemalloc.start(1)
    traced=[]; trace_peak=[0.,None]
    import ctypes
    class Mallinfo(ctypes.Structure):
        _fields_=[(k,ctypes.c_size_t) for k in ('arena','ordblks','smblks','hblks','hblkhd','usmblks','fsmblks','uordblks','fordblks','keepcost')]
    libc=ctypes.CDLL(None)
    libc.mallinfo2.restype=Mallinfo
    def allocator():
        v=libc.mallinfo2();return {k:getattr(v,k) for k,_ in Mallinfo._fields_}
    mark_original=mark
    def mark(name,**kw):
        mark_original(name,**kw)
        if name in ('first_solve_begin','factor_init_begin','factor_init_end','solve_end'):
            snap=tracemalloc.take_snapshot()
            traced.append(dict(event=name,id=kw.get('id'),rss=rss(),
                traced=tracemalloc.get_traced_memory(),allocator=allocator(),
                allocations=[dict(bytes=x.size,count=x.count,location=str(x.traceback)) for x in snap.statistics('lineno')[:30]]))
            del snap
            if name=='first_solve_begin' and spec.get('trim_allocator'):
                before=rss();libc.malloc_trim(0)
                traced[-1]['trim_resident_gib']=before-rss()
'''
s=s.replace('base_cgroup=cg();',insert+'\nbase_cgroup=cg();')
s=s.replace('tick+=1;stop.wait(.01)', '''if spec.get('trace_allocations') and samples[-1][1]>trace_peak[0]+.032:
            snap=tracemalloc.take_snapshot()
            trace_peak[:]=[samples[-1][1],dict(t=samples[-1][0],rss=samples[-1][1],traced=tracemalloc.get_traced_memory(),allocator=allocator(),
                allocations=[dict(bytes=x.size,count=x.count,location=str(x.traceback)) for x in snap.statistics('lineno')[:25]])]
            del snap
        tick+=1;stop.wait(.01)''')
s=s.replace('print(json.dumps(out,default=str))',"out['projection_requests']=projection_requests\nout['experimental_forecast']=getattr(S,'_study_forecasts',None)\nout['traced_allocations']=traced if spec.get('trace_allocations') else None\nout['trace_peak']=trace_peak if spec.get('trace_allocations') else None\nprint(json.dumps(out,default=str))")
s=s.replace('base_cgroup=cg();','base_io=me.io_counters()._asdict(); base_cgroup=cg();')
s=s.replace("out['experimental_forecast']=", "out['process_io_delta']={k:v-base_io[k] for k,v in me.io_counters()._asdict().items()}\nout['experimental_forecast']=")
(p/'profile_diagnostic.py').write_text(s)
