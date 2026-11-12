"""One isolated solve; observations never relax numerical or memory gates."""
import hashlib,json,os,resource,sys,time,traceback
from pathlib import Path
import numpy as np,psutil
from geometry_cases import build
from experiment_hooks import installed
HOOK_SOURCE_HASH=hashlib.sha256(Path(__file__).with_name('experiment_hooks.py').read_bytes()).hexdigest()

def main():
    root=Path(sys.argv[1]);spec=json.loads(sys.argv[2]);out=Path(spec['out'])
    sys.path.insert(0,str(root/'tools/GHOST'))
    from ghost_backend.geometry.io import parse_geometry,build_geometry_snapshot
    from ghost_backend.execution.options import cpu_allocation_scope
    from ghost_backend.execution.metrics import progress_listener
    from ghost_backend.twod import solver as S
    h=hashlib.sha256()
    for file in sorted((root/'tools/GHOST/ghost_backend').rglob('*.py')):
        h.update(file.relative_to(root).as_posix().encode()+b'\0'+file.read_bytes()+b'\0')
    cpu_start=resource.getrusage(resource.RUSAGE_SELF);start=time.monotonic();events=[];resources=[];factor_events=[];experiment_records=[]
    def event(kind,**kw):
        row=dict(t=time.monotonic()-start,event=kind,**kw)
        with open(str(out)+'.events.jsonl','a') as f:f.write(json.dumps(row,default=str)+'\n')
    gate0=S.evaluate_quality_gate
    def gate(*args,**kwargs):
        result=gate0(*args,**kwargs)
        event('quality_gate',gate=result)
        return result
    S.evaluate_quality_gate=gate
    resource0=S._dense_formulation_resources
    def describe(*args,**kwargs):
        r=resource0(*args,**kwargs);resources.append(r)
        event('resources',resources=r)
        return r
    S._dense_formulation_resources=describe
    from ghost_backend.linalg import dense
    init0=dense.DenseFactor.__init__
    def dense_init(self,a,*args,**kwargs):
        event('dense_factor_begin',n=len(a),matrix_bytes=a.nbytes)
        if spec.get('capture_matrix') and not factor_events:
            np.save(out.parent.parent/'matrices'/(spec['geometry_id']+'.npy'),a)
        try:return init0(self,a,*args,**kwargs)
        finally:
            e=getattr(self,'event',{});factor_events.append(e);event('dense_factor_end',details=e,condition_diagnostics=getattr(self,'diagnostics',None))
    dense.DenseFactor.__init__=dense_init
    from ghost_backend.execution import memory_budget as MB
    check0=MB.MemoryBudget._check
    def check(self,total,allowed,context,**details):
        if total>allowed:event('memory_rejection',required=total,allowed=allowed,context=context,plan=self.plan,details=details)
        return check0(self,total,allowed,context,**details)
    MB.MemoryBudget._check=check
    from ghost_backend.compressed.factor import CompressedFactor
    ci0=CompressedFactor.__init__
    def ci(self,a,*args,**kwargs):
        event('compressed_factor_begin',n=a.n,operator_bytes=a.bytes)
        try:return ci0(self,a,*args,**kwargs)
        finally:
            e=getattr(self,'event',{});factor_events.append(e);event('compressed_factor_end',details=e)
    CompressedFactor.__init__=ci
    scaled_lu=[]
    if spec.get('research_scaled_lu'):
        from research_hooks import install_scaled_lu
        scaled_lu=install_scaled_lu()
    if spec.get('force_hmatrix_rejection'):
        from ghost_backend.compressed import hmatrix
        def rejected(*a,**kw):raise hmatrix.HMatrixRejected('audit injected hierarchy assembly failure')
        hmatrix.build_pair=rejected
        hmatrix.HMatrixOperator=rejected
    if spec.get('research_balance'):
        from research_hooks import balance_closed_blocks
        balance_closed_blocks()
    if spec.get('research_loss_span'):
        from research_hooks import install_loss_span
        install_loss_span()
    if spec.get('research_leaf'):
        # Research-only geometry/representation tuning. The production planner
        # and allocator both read this constant; all accuracy gates stay intact.
        from ghost_backend.compressed import hmatrix
        hmatrix.LEAF=int(spec['research_leaf'])
    if spec.get('research_forecast'):
        from research_forecast import install
        install()
    if spec.get('fallback') or spec.get('full_fallback'):
        from ghost_backend.twod.assembly.native import far
        counts=[0]
        def unavailable(*args,**kwargs):counts[0]+=1;return None
        far.far_block=unavailable;far.tile_library=lambda:None;far.scatter_library=lambda:None
        if spec.get('full_fallback'):
            from ghost_backend.twod.assembly.native import near,table
            near.ENABLED=False
            table.library=lambda:None
    opts=dict(factorization=spec['backend'],mesh_strategy=spec.get('mesh_strategy','global'),
        basis_order=spec.get('degree',1),assembly_threads='auto',blas_threads='auto',
        compressed_storage_mib=0,ram_budget_gib=spec.get('cap',8.),
        dense_residual_storage=spec.get('storage','auto'))
    opts.update(spec.get('options',{}))
    text,geometry=build(spec)
    if spec.get('magnetic_thin_layer'):
        text=text.replace('Segment: body 2','Segment: body 1').replace('properties: 2 1 0 0 0','properties: 1 1 10 0 0')
        text=text.replace('IBCS_Resistances:\nDielectrics:', 'IBCS_Resistances:\n10 thin_dielectric 0.0001 1\nDielectrics:')+'1 2.0 -0.02 1.5 -0.01\n'
        geometry['material_model']='magnetic free-standing thin dielectric layer; PEC tag used only for contour generation'
    geo_path=out.parent.parent/'geometries'/(spec['geometry_id']+'.geo')
    geo_path.write_text(text)
    geometry['sha256']=hashlib.sha256(text.encode()).hexdigest()
    result=None;error=None;tb=None
    last_progress=[0.]
    def progress(*args,**kw):
        now=time.monotonic()
        if now-last_progress[0]>3:
            event('progress',args=args,kwargs=kw);last_progress[0]=now
    try:
        g=build_geometry_snapshot(*parse_geometry(text))
        with cpu_allocation_scope(spec.get('cpus',4)),progress_listener(progress),installed(spec) as experiment_records:
            if spec.get('polarization'):
                fn=S.solve_monostatic_rcs_2d_single_polarization
                extra=dict(polarization=spec['polarization'],compute_condition_number=True,strict_quality_gate=True)
            else:
                fn=S.solve_monostatic_rcs_2d_certified if spec.get('certified') else S.solve_monostatic_rcs_2d_survey
                extra={}
            result=fn(g,[spec['frequency_ghz']],list(np.linspace(0,180,spec.get('angles',19))),
                geometry_units='meters',max_panels=spec.get('max_panels',150000),execution_options=opts,**extra)
    except Exception as exc:error=type(exc).__name__+': '+str(exc);tb=traceback.format_exc()
    elapsed=time.monotonic()-start
    summary=dict(spec=spec,geometry=geometry,options=opts,error=error,traceback=tb,wall_seconds=elapsed,
        process_cpu_seconds=(resource.getrusage(resource.RUSAGE_SELF).ru_utime-cpu_start.ru_utime)+(resource.getrusage(resource.RUSAGE_SELF).ru_stime-cpu_start.ru_stime),source_sha256=h.hexdigest(),experiment_hooks_sha256=HOOK_SOURCE_HASH,hook_hash_time='module_start',rss_highwater_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2,
        resources=resources,factor_events=factor_events,scaled_lu_factors=scaled_lu,experiment_records=experiment_records,fallback_calls=counts[0] if (spec.get('fallback') or spec.get('full_fallback')) else 0)
    if result is not None:
        meta=result['metadata'];samples=result['samples']
        field=np.array([complex(s['rcs_amp_real'],s['rcs_amp_imag']) for s in samples])
        np.savez_compressed(str(out)+'.npz',field=field)
        Path(str(out)+'.metadata.json').write_text(json.dumps(meta,default=str))
        Path(str(out)+'.samples.json').write_text(json.dumps(samples,default=str))
        summary.update(quality_gate=meta.get('quality_gate'),fields_count=len(field),
            stages=meta.get('stage_seconds'),backend_selection=meta.get('backend_selection'),
            actual_unknowns=max([r['system_dofs'] for r in resources] or [0]))
    Path(str(out)+'.json').write_text(json.dumps(summary,indent=2,default=str)+'\n')
    print(json.dumps(dict(case=spec['case'],wall=round(elapsed,2),rss=round(summary['rss_highwater_gib'],3),
        unknowns=summary.get('actual_unknowns'),error=error)),flush=True)

if __name__=='__main__':main()
