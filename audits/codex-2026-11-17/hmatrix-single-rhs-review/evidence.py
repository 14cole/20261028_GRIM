"""Package/restore exact fresh files, with hashes for archive parts and members."""
import hashlib,io,json,sys,tarfile
from pathlib import Path
R=Path(__file__).resolve().parent;E=R/'evidence'
sha=lambda b:hashlib.sha256(b).hexdigest()
if sys.argv[1]=='pack':
    E.mkdir(exist_ok=True);buf=io.BytesIO();members={}
    with tarfile.open(fileobj=buf,mode='w') as tar:
        for p in sorted((R/'fresh').iterdir()):
            if not p.is_file():continue
            b=p.read_bytes();members[p.name]=dict(bytes=len(b),sha256=sha(b))
            info=tarfile.TarInfo(p.name);info.size=len(b);info.mtime=0
            tar.addfile(info,io.BytesIO(b))
    data=buf.getvalue();parts=[]
    for start in range(0,len(data),4*1024**2):
        b=data[start:start+4*1024**2];name=f'fresh.tar.part{len(parts):03d}'
        (E/name).write_bytes(b);parts.append(dict(name=name,bytes=len(b),sha256=sha(b)))
    manifest=dict(bytes=len(data),sha256=sha(data),parts=parts,members=members)
    (E/'MANIFEST.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(dict(bytes=len(data),parts=len(parts),members=len(members))))
elif sys.argv[1]=='unpack':
    target=Path(sys.argv[2]);target.mkdir(parents=True,exist_ok=True)
    m=json.loads((E/'MANIFEST.json').read_text());chunks=[]
    for p in m['parts']:
        b=(E/p['name']).read_bytes();assert len(b)==p['bytes'] and sha(b)==p['sha256'];chunks.append(b)
    data=b''.join(chunks);assert len(data)==m['bytes'] and sha(data)==m['sha256']
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:') as tar:
        assert set(tar.getnames())==set(m['members'])
        for info in tar.getmembers():
            assert info.isfile() and Path(info.name).name==info.name
            p=target/info.name;assert not p.exists(),p
            b=tar.extractfile(info).read();expected=m['members'][info.name]
            assert len(b)==expected['bytes'] and sha(b)==expected['sha256'];p.write_bytes(b)
    print(json.dumps(dict(restored_members=len(m['members']),all_hashes_verified=True)))
else:raise ValueError('Use pack or unpack TARGET')
