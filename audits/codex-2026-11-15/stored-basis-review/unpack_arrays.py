"""Restore full arrays without changing one bit; verifies archive and each array.
Usage: python unpack_arrays.py /absolute/output/directory
Output: results/<case>.npz (consolidated across original batches).
"""
import sys,json,hashlib,lzma,io,tarfile,tempfile
from pathlib import Path
import numpy as np
sha=lambda x:hashlib.sha256(x).hexdigest()
def restore(source,destination):
    m=json.loads((source/'ARRAYS_MANIFEST.json').read_text());digest=hashlib.sha256()
    with tempfile.TemporaryFile() as archive:
        for p in m['parts']:
            data=(source/p['name']).read_bytes();assert len(data)==p['bytes'] and sha(data)==p['sha256'];archive.write(data);digest.update(data)
        assert archive.tell()==m['archive_bytes'] and digest.hexdigest()==m['archive_sha256'];archive.seek(0)
        with tarfile.open(fileobj=archive,mode='r') as tar:
            index=json.load(tar.extractfile('arrays-index.json'));cache={}
            def raw(h):
                if h in cache:return cache[h]
                ob=index['objects'][h];packed=tar.extractfile('payload/'+h+'.xz').read();assert sha(packed)==ob['payload_sha256']
                value=lzma.decompress(packed)
                if ob['encoding']=='xor':value=np.bitwise_xor(np.frombuffer(value,np.uint8),np.frombuffer(raw(ob['base']),np.uint8)).tobytes()
                else:assert ob['encoding']=='raw'
                assert len(value)==ob['bytes'] and sha(value)==h;cache[h]=value;return value
            out=destination/'results';out.mkdir(parents=True,exist_ok=True)
            for label,case in index['cases'].items():
                if Path(label).name!=label or label in ('.','..'):raise ValueError('Unsafe case name')
                values={k:np.frombuffer(raw(v['object']),dtype=v['dtype']).reshape(v['shape']) for k,v in case['arrays'].items()}
                np.savez_compressed(out/(label+'.npz'),**values);cache.clear();print(label,flush=True)
            for name,meta in index.get('records_files',{}).items():
                if Path(name).name!=name:raise ValueError('Unsafe record name')
                data=tar.extractfile('records/'+name).read()
                assert len(data)==meta['bytes'] and sha(data)==meta['sha256']
                (out/name).write_bytes(data)
            for name,meta in index.get('logs_files',{}).items():
                if Path(name).name!=name:raise ValueError('Unsafe log name')
                data=tar.extractfile('logs/'+name).read()
                assert len(data)==meta['bytes'] and sha(data)==meta['sha256']
                (out/name).write_bytes(data)
            for member in tar.getmembers():
                if member.name.startswith('partial/'):
                    name=Path(member.name).name;(out/name).write_bytes(tar.extractfile(member).read())
    return len(index['cases'])
if __name__=='__main__':print('Restored',restore(Path(__file__).resolve().parent,Path(sys.argv[1]).resolve()),'cases')
