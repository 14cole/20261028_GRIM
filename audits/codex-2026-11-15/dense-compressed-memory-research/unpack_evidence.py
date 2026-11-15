"""Restore every saved array bit and every result/log. No pickle or tar extraction.
Usage: python unpack_evidence.py /absolute/empty/output_directory
"""
import io,json,lzma,hashlib,tarfile,tempfile,sys
from pathlib import Path
import numpy as np
sha=lambda x:hashlib.sha256(x).hexdigest()
def restore(source,destination):
    manifest=json.loads((source/'MANIFEST.json').read_text());digest=hashlib.sha256()
    out=destination/'results';out.mkdir(parents=True,exist_ok=True)
    def safe(name):
        if Path(name).name!=name or name in ('.','..'):raise ValueError('Unsafe filename')
        return name
    with tempfile.TemporaryFile() as archive:
        for p in manifest['parts']:
            data=(source/safe(p['name'])).read_bytes();assert len(data)==p['bytes'] and sha(data)==p['sha256']
            digest.update(data);archive.write(data)
        assert archive.tell()==manifest['archive_bytes'] and digest.hexdigest()==manifest['archive_sha256']
        archive.seek(0)
        with tarfile.open(fileobj=archive,mode='r') as tar:
            index=json.load(tar.extractfile('index.json'));cache={}
            def raw(h):
                if h in cache:return cache[h]
                assert len(h)==64 and all(c in '0123456789abcdef' for c in h)
                ob=index['objects'][h];packed=tar.extractfile('payload/'+h+'.xz').read();assert sha(packed)==ob['payload_sha256']
                data=lzma.decompress(packed)
                data=np.frombuffer(data,np.uint8).reshape(ob['byte_shuffle'],-1).T.copy().tobytes()
                if ob['encoding']=='xor':data=np.bitwise_xor(np.frombuffer(data,np.uint8),np.frombuffer(raw(ob['base']),np.uint8)).tobytes()
                else:assert ob['encoding']=='raw'
                assert len(data)==ob['bytes'] and sha(data)==h;cache[h]=data;return data
            for name,descs in index['arrays'].items():
                arrays={}
                for key,d in descs.items():
                    a=np.frombuffer(raw(d['object']),dtype=d['dtype']).reshape(d['shape'])
                    if 'slice' in d:
                        s=d['slice'];sl=[slice(None)]*a.ndim;sl[s['axis']]=slice(s['start'],s['stop']);a=a[tuple(sl)]
                    arrays[key]=np.asfortranarray(a) if d['fortran'] else np.ascontiguousarray(a)
                np.savez_compressed(out/safe(name),**arrays)
                if sum(map(len,cache.values()))>256*1024**2:cache.clear()
            for name,meta in index['records'].items():
                data=tar.extractfile('results/'+safe(name)).read();assert len(data)==meta['bytes'] and sha(data)==meta['sha256']
                (out/name).write_bytes(data)
    return dict(array_files=len(index['arrays']),records=len(index['records']),all_object_hashes_verified=True)
if __name__=='__main__':print(json.dumps(restore(Path(__file__).resolve().parent/'evidence',Path(sys.argv[1]).resolve())))
