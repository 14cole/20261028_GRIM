"""Losslessly pack complete reference/candidate blocks as reference + XOR bits.
XOR acts on IEEE-754 bits, not floating-point subtraction. The archive retains
every output bit and a SHA-256 for each reconstructed complex array.
Reference bytes are transposed by byte position before ZIP compression.
Observer-normal reference K uses another lossless XOR against transposed
source-normal K; S uses the identical source-normal reference as its base.
"""
import hashlib,json
from pathlib import Path
import numpy as np
def transpose_reference(value):
 # Normal derivatives transpose the double-layer matrix. S is unchanged.
 # XOR is still lossless if floating-point evaluation breaks exact symmetry.
 n=int(round(np.sqrt(value.shape[1])));assert n*n==value.shape[1]
 result=value.copy();result[1]=value[1].reshape(n,n,2,2).transpose(1,0,3,2).reshape(n*n,2,2)
 return np.ascontiguousarray(result)
def pack(path,arrays):
 packed={};checks={}
 for name,value in arrays.items():
  value=np.ascontiguousarray(value);checks[name]=dict(shape=value.shape,dtype=str(value.dtype),sha256=hashlib.sha256(value.tobytes()).hexdigest())
  if name.endswith('_native'):
   ref=np.ascontiguousarray(arrays[name[:-7]+'_reference']);packed[name+'_xor']=np.bitwise_xor(value.view(np.uint64),ref.view(np.uint64))
  elif '-True_reference' in name:
   base=transpose_reference(arrays[name.replace('-True_reference','-False_reference')]);packed[name+'_transpose_xor']=np.bitwise_xor(value.view(np.uint64),base.view(np.uint64))
  else:packed[name+'_bytes']=value.view(np.uint8).reshape(-1,16).T.copy()
 np.savez_compressed(path,**packed)
 Path(str(path)+'.arrays.json').write_text(json.dumps(checks,indent=2))
def unpack(path):
 data=np.load(path);checks=json.loads(Path(str(path)+'.arrays.json').read_text());arrays={}
 def reference(name):
  if '-True_reference' in name:
   base=transpose_reference(reference(name.replace('-True_reference','-False_reference')))
   return np.bitwise_xor(data[name+'_transpose_xor'],base.view(np.uint64)).view(np.complex128)
  return data[name+'_bytes'].T.copy().view(np.complex128).reshape(checks[name]['shape'])
 for name,meta in checks.items():
  if name.endswith('_native'):
   ref=reference(name[:-7]+'_reference');value=np.bitwise_xor(data[name+'_xor'],ref.view(np.uint64)).view(np.complex128)
  else:value=reference(name)
  assert list(value.shape)==meta['shape'] and str(value.dtype)==meta['dtype']
  assert hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()==meta['sha256'],name
  arrays[name]=value
 return arrays
if __name__=='__main__':
 import sys
 arrays=unpack(Path(sys.argv[1]));print('Verified and reconstructed',len(arrays),'complete arrays')
 if len(sys.argv)>2:np.savez_compressed(sys.argv[2],**arrays)
