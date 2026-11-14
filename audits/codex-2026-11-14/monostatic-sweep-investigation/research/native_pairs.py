"""Research-only native fixed-near integration. No production module is edited.
Uses the existing screened table and quadrature classifier. The paired ABI
avoids an N-by-N Cartesian output for N requested pairs. Unsupported inputs,
missing/unqualified tables and below-domain distances retain the reference.
"""
import ctypes as ct
from pathlib import Path
import numpy as np
from ghost_backend.twod import operators as op
from ghost_backend.twod.assembly.native import far
from ghost_backend.twod.polynomial_quadrature import _kernel_table
original=op._integrate_linear_pairs_box_sk_batched
fun=ct.CDLL(str(Path(__file__).with_name('libpaired_kernel.so'))).ghost_pair_block
fun.argtypes=far.library().argtypes;fun.restype=ct.c_int
stats=dict(calls=0,pairs=0,fallback_calls=0)
def fixed(elements,obs_indices,src_indices,k0,obs_normal_deriv,order,compute_single_layer=True,compute_double_layer=True,prepared_geometry=None):
 args=(elements,obs_indices,src_indices,k0,obs_normal_deriv,order,compute_single_layer,compute_double_layer)
 def fallback():
  stats['fallback_calls']+=1
  return original(*args,prepared_geometry=prepared_geometry)
 oi=np.asarray(obs_indices,dtype=np.int64).reshape(-1);si=np.asarray(src_indices,dtype=np.int64).reshape(-1);n=len(oi);k=complex(k0)
 if len(si)!=n or not n or prepared_geometry is None or len(elements[0].node_ids)!=2 or k.real<=0 or k.imag>0:return fallback()
 p0,p1,segments,lengths,normals=prepared_geometry
 reach=max(float(np.max(np.linalg.norm(a[oi]-b[si],axis=1))) for a in (p0,p1) for b in (p0,p1))
 if reach<=0 or not np.isfinite(reach):return fallback()
 table=_kernel_table(k.real,k.imag,float(2**np.ceil(np.log2(reach*(1+1e-9)))))
 if table is None or not table.native_checked:return fallback()
 q,w=op._get_quadrature(max(2,int(order)));phi=np.ascontiguousarray(op._polynomial_values(q,1));w=np.ascontiguousarray(w)
 obs=np.ascontiguousarray(p0[oi,None]+q[None,:,None]*segments[oi,None]);src=np.ascontiguousarray(p0[si,None]+q[None,:,None]*segments[si,None])
 on=np.ascontiguousarray(normals[oi]);sn=np.ascontiguousarray(normals[si]);mask=np.ones(n,np.uint8)
 s=np.zeros((4,n),complex);d=np.zeros_like(s);bounds=table.bounds;coeff=table.normalized_power
 status=fun(n,n,len(q),2,obs.ctypes.data,src.ctypes.data,w.ctypes.data,phi.ctypes.data,on.ctypes.data,sn.ctypes.data,mask.ctypes.data,int(obs_normal_deriv),int(compute_single_layer),int(compute_double_layer),0,k.real,k.imag,len(bounds)-1,bounds.ctypes.data,coeff.shape[1]-1,coeff.ctypes.data,s.ctypes.data if compute_single_layer else None,d.ctypes.data if compute_double_layer else None,None)
 if status:return fallback()
 scale=(lengths[oi]*lengths[si])[:,None,None];stats['calls']+=1;stats['pairs']+=n
 return s.T.reshape(n,2,2)*scale,d.T.reshape(n,2,2)*scale
def install():op._integrate_linear_pairs_box_sk_batched=fixed
