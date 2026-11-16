"""Lossless arrays, consolidated across angle batches then XOR/LZMA compressed.
All results/logs/geometries are also included. Original NPZ byte hashes are
provenance; restoration promises numerical-array bits and layout, not ZIP bytes.
"""
import io,json,lzma,hashlib,tarfile
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
sha=lambda x:hashlib.sha256(x).hexdigest()
def main():
    pub=ROOT/'evidence';pub.mkdir(exist_ok=True)
    payload=ROOT/'payload';payload.mkdir(exist_ok=True)
    objects={};references={};files={};source={}
    def add(value,key,group):
        value=np.asarray(value);raw=np.ascontiguousarray(value).tobytes();h=sha(raw)
        refkey=(group,key,value.shape,value.dtype.str)
        if h not in objects:
            ref=references.get(refkey);data=raw;enc='raw';base=None
            if ref is not None:
                base,refpath=ref
                old=refpath.read_bytes()
                data=np.bitwise_xor(np.frombuffer(raw,np.uint8),np.frombuffer(old,np.uint8)).tobytes();enc='xor'
            stride=value.dtype.itemsize
            data=np.frombuffer(data,np.uint8).reshape(-1,stride).T.copy().tobytes()
            packed=lzma.compress(data,preset=3);(payload/(h+'.xz')).write_bytes(packed)
            objects[h]=dict(bytes=len(raw),encoding=enc,base=base,byte_shuffle=stride,payload_sha256=sha(packed),payload_bytes=len(packed))
        if refkey not in references:
            path=payload/(h+'.raw');path.write_bytes(raw);references[refkey]=(h,path)
        return dict(object=h,shape=value.shape,dtype=value.dtype.str)
    specs={}
    for suite in ROOT.glob('suite*.json'):
        specs.update(json.loads(suite.read_text()))
    labels=sorted(specs,key=lambda x:(specs[x].get('method')!='dense',x))
    used=set()
    for label in labels:
        spec=specs[label]
        group=json.dumps({k:v for k,v in spec.items() if k not in ('runner','method','packing','residual','row_block','batch','threads','storage_mib','builder','hook','rank_guard','inverse_tolerance','leaf_scaling','audit','direct_query','price_leaf_queries')},sort_keys=True)
        paths=sorted((ROOT/'results').glob(label+'-batch*.npz'))
        if paths:
            blocks=[]
            for p in paths:
                with np.load(p) as z:blocks.append({k:z[k] for k in z.files})
            merged={}
            for key in blocks[0]:
                if key in ('rows','row_norm'):
                    assert all(np.array_equal(blocks[0][key],b[key]) for b in blocks)
                    v=blocks[0][key]
                else:v=np.concatenate([b[key] for b in blocks],axis=1 if key in ('density','rhs','residual') else 0)
                merged[key]=add(v,key,group)
            start=0
            for p,b in zip(paths,blocks):
                count=len(b['angles']);descriptors={}
                for key,a in b.items():
                    desc=dict(merged[key]);desc['fortran']=bool(a.flags.f_contiguous and not a.flags.c_contiguous)
                    if key not in ('rows','row_norm'):desc['slice']=dict(axis=1 if key in ('density','rhs','residual') else 0,start=start,stop=start+count)
                    descriptors[key]=desc
                files[p.name]=descriptors;source[p.name]=dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes()));used.add(p);start+=count
            del blocks,merged
        for p in sorted((ROOT/'results').glob(label+'-*.npz')):
            if p in used:continue
            with np.load(p) as z:
                files[p.name]={}
                for key in z.files:
                    a=z[key];files[p.name][key]=dict(add(a,key,group),fortran=bool(a.flags.f_contiguous and not a.flags.c_contiguous))
            source[p.name]=dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes()));used.add(p)
        print(label,flush=True)
    assert used==set((ROOT/'results').glob('*.npz'))
    records={p.name:dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted((ROOT/'results').iterdir()) if p.is_file() and p.suffix!='.npz'}
    index=dict(format='dense-compressed-lossless-v1',objects=objects,arrays=files,original_npz=source,records=records)
    archive=pub/'evidence.tar'
    with tarfile.open(archive,'w') as tar:
        def put(name,data):
            ti=tarfile.TarInfo(name);ti.size=len(data);ti.mtime=0;tar.addfile(ti,io.BytesIO(data))
        put('index.json',json.dumps(index,sort_keys=True).encode())
        for h in objects:put('payload/'+h+'.xz',(payload/(h+'.xz')).read_bytes())
        for name in records:put('results/'+name,(ROOT/'results'/name).read_bytes())
    parts=[];digest=hashlib.sha256()
    with archive.open('rb') as f:
        i=0
        while data:=f.read(4*1024**2):
            name=f'evidence.tar.part{i:03d}';(pub/name).write_bytes(data);digest.update(data)
            parts.append(dict(name=name,bytes=len(data),sha256=sha(data)));i+=1
    manifest=dict(format=index['format'],archive_bytes=archive.stat().st_size,archive_sha256=digest.hexdigest(),array_files=len(files),objects=len(objects),records=len(records),parts=parts)
    (pub/'MANIFEST.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest),flush=True)
if __name__=='__main__':main()
