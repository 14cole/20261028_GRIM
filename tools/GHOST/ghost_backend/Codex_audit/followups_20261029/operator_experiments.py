"""Controlled operator experiments; never calibrate production admission here."""
import argparse
from collections import OrderedDict
import gc
import json
import os
from pathlib import Path
import sys
import threading
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT.parent),str(ROOT/'tests')]
os.environ.update(OPENBLAS_NUM_THREADS='4',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4')
import numpy as np
from ghost_backend.compressed import hmatrix as H
from ghost_backend.compressed.hmatrix_factor import HMatrixFactor
from ghost_backend.compressed.factor import CompressedFactor
from ghost_backend.execution.options import validate_options,execution_scope


def save(name,data):
    (HERE/name).write_text(json.dumps(data,indent=2,default=str),encoding='utf-8')


def loss_study(panels_per_edge=64,output='loss_study.json'):
    from capacity_probe import geometry
    from ghost_backend.twod import solver as s
    from ghost_backend.compressed.coefficients import NativeOracle
    from ghost_backend.compressed.runtime import coordinates
    options=validate_options(dict(factorization='compressed',mesh_strategy='global',basis_order=2,
        mesh_grading=False,enforce_mesh_density=False,assembly_threads=4,blas_threads=4,ram_budget_gib=8))
    snapshot=geometry('inlet_high_contrast')
    snapshot['segments'][0]['properties'][1]=str(panels_per_edge)
    frequency=1.;k0=2*np.pi*frequency*1e9/s.C0
    material=lambda loss:s.MaterialLibrary.from_entries([], [['1','101.19',str(-11.88*loss),'3.45',str(-3.47*loss)]],base_dir='.')
    rows=[]
    with execution_scope(options):
        initial=material(1.)
        panels=s._build_panels(snapshot,.0254,s._mesh_wavelength_for_snapshot(snapshot,initial,frequency)[0])
        infos=s._build_coupled_panel_info(panels,initial,frequency,'TE',k0)
        mesh,_=s._build_linear_mesh_interface_aware(panels,infos)
        assert 500 <= len(mesh.nodes) <= 2048,len(mesh.nodes)
        # Fix both inverse policy and mesh. This is an algebraic calibration
        # experiment, not a claim that this coarse mesh resolves the fields.
        import ghost_backend.compressed.factor as F
        F.PRECONDITIONER_TOLERANCE=1e-10
        F.CompressedFactor._upgrade_preconditioner=lambda self:False
        for loss in (0.,.25,1.):
            for pol in ('TE','TM'):
                row=dict(loss_multiplier=loss,polarization=pol,nodes=len(mesh.nodes),panels=len(panels),
                    frequency_ghz=frequency,inverse_tolerance=1e-10,mesh_convergence_certified=False)
                started=time.perf_counter()
                oracle=op=factor=None
                try:
                    infos=s._build_linear_coupled_infos(mesh,material(loss),frequency,pol,k0)
                    oracle=NativeOracle(mesh,infos,pol,k0,'dielectric')
                    xy=coordinates(mesh,oracle.n);radius=H.support_radius(mesh,xy)
                    waves=[complex(v) for i in infos for v in (i.k_minus,i.k_plus)]
                    forecast=H.forecast_storage(xy,radius,max(map(abs,waves)))
                    row.update(unknowns=oracle.n,interior_wavenumber=str(oracle.k1),
                        forecast_inverse_rank=forecast['inverse_rank'],forecast_inverse_bytes=forecast['inverse_bytes'])
                    op=H.HMatrixOperator(oracle,xy,radius,budget=2*1024**3)
                    factor=HMatrixFactor(op,storage_budget_bytes=2*1024**3)
                    rng=np.random.default_rng(20261029)
                    b=rng.standard_normal((oracle.n,3))+1j*rng.standard_normal((oracle.n,3))
                    x=factor.solve(b)
                    # Independent full-row streamed residual, without a dense
                    # reference matrix or a second physical approximation.
                    residual=np.zeros(3);norm=0.
                    for start in range(0,oracle.n,64):
                        ids=np.arange(start,min(start+64,oracle.n))
                        exact,tail=oracle.get_with_error(ids,np.arange(oracle.n))
                        norm=max(norm,float(np.max(np.sum(abs(exact),axis=1))))
                        residual=np.maximum(residual,np.max(abs(exact@x-b[ids])+tail@abs(x),axis=0))
                    error=float(np.max(residual/(norm*np.max(abs(x),axis=0)+np.max(abs(b),axis=0))))
                    assert error<=1e-12,error
                    row.update(status='passed',operator_bytes=op.bytes,operator_rank=op.evidence['max_rank'],
                        inverse_bytes=factor.factor.bytes,inverse_rank=factor.factor.evidence['max_rank'],
                        full_streamed_backward_error=error,sampled_row_error=op.sampled_row_error)
                except Exception as exc:
                    row.update(status='rejected',error_type=type(exc).__name__,reason=str(exc))
                finally:
                    factor=op=oracle=None;gc.collect()
                row['seconds']=time.perf_counter()-started
                rows.append(row);save(output,rows)
                print(json.dumps(row),flush=True)


def reciprocal_study():
    from test_hmatrix_2026_10_17 import Kernel
    class CachedKernel(Kernel):
        def __init__(self):
            super().__init__(1200)
            self.cache=OrderedDict();self.cache_bytes=0;self.peak=0
            self.hits=self.reciprocal_hits=self.saved_entries=0
            self.lock=threading.RLock()
        def get_with_error(self,rows,cols):
            key=(np.asarray(rows,np.int64).tobytes(),np.asarray(cols,np.int64).tobytes())
            reverse=key[::-1]
            with self.lock:
                found=key if key in self.cache else reverse if reverse in self.cache else None
                if found is not None:
                    value=self.cache.pop(found);self.cache[found]=value
                    self.hits+=1;self.reciprocal_hits+=found!=key;self.saved_entries+=len(rows)*len(cols)
                    return (value[0].copy(),value[1].copy()) if found==key else (value[0].T.copy(),value[1].T.copy())
            value=super().get_with_error(rows,cols)
            size=sum(a.nbytes for a in value)+sum(map(len,key))
            if size<=32*1024**2:
                with self.lock:
                    if key in self.cache:return value
                    while self.cache_bytes+size>32*1024**2:
                        old,arrays=self.cache.popitem(last=False)
                        self.cache_bytes-=sum(a.nbytes for a in arrays)+sum(map(len,old))
                    self.cache[key]=value;self.cache_bytes+=size;self.peak=max(self.peak,self.cache_bytes)
            return value
    options=validate_options(dict(assembly_threads=4,blas_threads=4))
    rows=[]
    with execution_scope(options):
        for cached in (False,True):
            source=CachedKernel() if cached else Kernel(1200)
            assert np.array_equal(source.dense,source.dense.T)
            op=H.HMatrixOperator(source,source.xy,np.full(source.n,source.h),budget=1024**3)
            factor=HMatrixFactor(op,storage_budget_bytes=1024**3)
            b=np.exp(1j*np.arange(source.n))[:,None]
            x=factor.solve(b)
            reference=np.linalg.solve(source.dense,b)
            error=float(np.max(abs(x-reference))/np.max(abs(reference)))
            assert error<1e-10,error
            rows.append(dict(cached=cached,oracle_entries=source.entries,oracle_calls=source.calls,
                cache_hits=getattr(source,'hits',0),reciprocal_hits=getattr(source,'reciprocal_hits',0),
                saved_entries=getattr(source,'saved_entries',0),cache_peak_bytes=getattr(source,'peak',0),
                relative_solution_difference=error,sampled_row_error=op.sampled_row_error))
            del factor,op,source;gc.collect()
    save('reciprocal_query_study.json',dict(scope='Symmetric scalar test kernel only; not a material-system symmetry assumption or a timing benchmark.',runs=rows))
    print(json.dumps(rows),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('study',choices=['loss','reciprocal'])
    parser.add_argument('--panels-per-edge',type=int,default=64)
    parser.add_argument('--output',default='loss_study.json')
    args=parser.parse_args()
    loss_study(args.panels_per_edge,args.output) if args.study=='loss' else reciprocal_study()
