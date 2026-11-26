"""Hash every binary and C source named in NATIVE_LIBRARIES*.json; check exports (ELF: ctypes load; PE: export table parse)."""
import ctypes, hashlib, json, struct, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()   # tools/GHOST
def pe_exports(data):
    pe = struct.unpack_from('<I', data, 0x3c)[0]; nsec = struct.unpack_from('<H', data, pe+6)[0]
    opt = pe+24; magic = struct.unpack_from('<H', data, opt)[0]; assert magic == 0x20b
    rva = struct.unpack_from('<I', data, opt+112)[0]; sec = opt+struct.unpack_from('<H', data, pe+20)[0]
    secs = [struct.unpack_from('<IIII', data, sec+40*i+8) for i in range(nsec)]
    off = lambda r: next(r-va+raw for vs, va, rs, raw in secs if va <= r < va+max(vs, rs))
    n, names = struct.unpack_from('<I', data, off(rva)+24)[0], struct.unpack_from('<I', data, off(rva)+32)[0]
    out = []
    for i in range(n):
        p = off(struct.unpack_from('<I', data, off(names)+4*i)[0]); out.append(data[p:data.index(b'\0', p)].decode())
    return out
rows, ok = [], True
for manifest in ('NATIVE_LIBRARIES.json', 'NATIVE_LIBRARIES_LINUX.json'):
    for lib in json.loads((root/manifest).read_text())['libraries']:
        data, src = (root/lib['path']).read_bytes(), (root/lib['source']).read_bytes()
        row = dict(manifest=manifest, path=lib['path'], bytes_ok=len(data) == lib['bytes'],
                   sha_ok=hashlib.sha256(data).hexdigest() == lib['sha256'],
                   source_sha_ok=hashlib.sha256(src).hexdigest() == lib['source_sha256'])
        if lib['path'].endswith('.dll'):
            exports = pe_exports(data); row['exports_ok'] = set(lib['required_exports']) <= set(exports)
        else:
            dll = ctypes.CDLL(str(root/lib['path'])); row['exports_ok'] = all(hasattr(dll, n) for n in lib['required_exports'])
        row['n_required_exports'] = len(lib['required_exports'])
        ok &= all(v for k, v in row.items() if k.endswith('_ok')); rows.append(row)
print(json.dumps(dict(all_ok=ok, rows=rows), indent=1)); sys.exit(0 if ok else 1)
