"""Lossless full-array evidence, deduplicated and XOR-delta encoded.

Consolidates successful batch archives; keeps every complex density/RHS/field
value and every exact-row residual. SHA256 is checked per reconstructed array.
Failed partial NPZs are kept verbatim separately in the archive.
"""
import io,json,lzma,hashlib,tarfile
from pathlib import Path
import numpy as np
from evidence_paths import batches
ROOT=Path(__file__).resolve().parent
sha=lambda x:hashlib.sha256(x).hexdigest()

def main():
    pub=ROOT/'publication';pub.mkdir(exist_ok=True)
    records=[]
    for p in (ROOT/'results').glob('*.json'):
        if p.name.endswith('.time.json'):continue
        d=json.loads(p.read_text());t=p.with_suffix('.time.json')
        if 'spec' in d and t.exists() and json.loads(t.read_text())['returncode']==0:records.append((p.stem,d))
    records.sort(key=lambda z:(z[1]['spec']['method']!='dense',z[0]))
    objects={};references={};cases={};payloads={}
    def add_array(value,key,group):
        value=np.ascontiguousarray(value);raw=value.tobytes();h=sha(raw)
        if h not in objects:
            ref=references.get((group,key,value.shape,value.dtype.str));enc='raw';data=raw;refhash=None
            if ref is not None:
                refhash,old=ref
                data=np.bitwise_xor(np.frombuffer(raw,np.uint8),np.frombuffer(old,np.uint8)).tobytes();enc='xor'
            packed=lzma.compress(data,preset=3)
            objects[h]=dict(bytes=len(raw),sha256=h,encoding=enc,base=refhash,payload_sha256=sha(packed),payload_bytes=len(packed))
            payloads[h]=packed
        references.setdefault((group,key,value.shape,value.dtype.str),(h,raw))
        return dict(object=h,shape=value.shape,dtype=value.dtype.str)
    for label,d in records:
        paths=batches(ROOT/'results',label);blocks=[]
        for p in paths:
            with np.load(p,allow_pickle=False) as z:blocks.append({k:z[k] for k in z.files})
        assert blocks,label
        s=d['spec'];group=tuple(s.get(k,v) for k,v in [('n',None),('k',None),('geometry','star'),('pol','TE'),('count',None),('start',0.),('stop',360.)])
        merged={}
        for key in blocks[0]:
            if key in ('rows','row_norm'):
                assert all(np.array_equal(blocks[0][key],b[key]) for b in blocks);value=blocks[0][key]
            else:value=np.concatenate([b[key] for b in blocks],axis=1 if key in ('density','rhs','residual') else 0)
            merged[key]=add_array(value,key,group)
        cases[label]=dict(arrays=merged,source_batches=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in paths])
        print(label,flush=True)
        del blocks,merged
    records_files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in (ROOT/'results').glob('*.json')}
    logs_files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for pattern in ('*.stdout','*.stderr') for p in (ROOT/'results').glob(pattern)}
    manifest=dict(format='monostatic-lossless-arrays-v1',objects=objects,cases=cases,records_files=records_files,logs_files=logs_files)
    archive=pub/'arrays.tar'
    with tarfile.open(archive,'w') as tar:
        def add(name,data):
            ti=tarfile.TarInfo(name);ti.size=len(data);ti.mtime=0;tar.addfile(ti,io.BytesIO(data))
        add('arrays-index.json',json.dumps(manifest,sort_keys=True).encode())
        for h,data in payloads.items():add('payload/'+h+'.xz',data)
        for name in records_files:add('records/'+name,(ROOT/'results'/name).read_bytes())
        for name in logs_files:add('logs/'+name,(ROOT/'results'/name).read_bytes())
        successful=set(cases)
        for p in (ROOT/'results').glob('*-batch*.npz'):
            label=p.name.rsplit('-batch',1)[0]
            if label not in successful:add('partial/'+p.name,p.read_bytes())
    parts=[];digest=hashlib.sha256()
    with archive.open('rb') as f:
        i=0
        while data:=f.read(4*1024**2):
            digest.update(data);name=f'arrays.tar.part{i:03d}';(pub/name).write_bytes(data);parts.append(dict(name=name,bytes=len(data),sha256=sha(data)));i+=1
    (pub/'ARRAYS_MANIFEST.json').write_text(json.dumps(dict(format=manifest['format'],archive_bytes=archive.stat().st_size,archive_sha256=digest.hexdigest(),parts=parts,cases={k:v['arrays'] for k,v in cases.items()}),indent=2))
    print(json.dumps(dict(cases=len(cases),objects=len(objects),archive_bytes=archive.stat().st_size,parts=len(parts))),flush=True)
if __name__=='__main__':main()
