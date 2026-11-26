"""Independent build + content inspection of the GHOST wheel, sdist and source ZIP.

usage: build_and_inspect.py GRIM_CHECKOUT WORKDIR OUT.json [--fix]
Exports ed90b65 with `git archive`, builds in the export (never in the checkout),
and reports where vendored notices and runtime files are present.  --fix applies
the proposed package-data change to the disposable export first.
"""
import hashlib, json, subprocess, sys, tarfile, zipfile, shutil, io
from pathlib import Path

COMMIT = 'ed90b65ff89826274adacae01bcfbafe143e9819'
repo, work, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve()
fix = '--fix' in sys.argv
shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
src = work/'src'; src.mkdir()
tar = subprocess.run(['git', '-C', str(repo), 'archive', COMMIT], check=True, capture_output=True).stdout
tarfile.open(fileobj=io.BytesIO(tar)).extractall(src, filter='data')
ghost = src/'tools/GHOST'
sha = lambda b: hashlib.sha256(b).hexdigest()
if fix:
    p = ghost/'pyproject.toml'; t = p.read_text()
    anchor = '[tool.setuptools.package-data]\n'
    assert anchor in t
    p.write_text(t.replace(anchor, anchor + '"ghost_backend.execution.thread_control" = ["LICENSE-3.6.0.txt"]\n'))

art = work/'artifacts'; art.mkdir()
# 1. PEP 517 build in isolated env (python -m build)
r = subprocess.run([sys.executable, '-m', 'build', '--wheel', '--sdist', '--outdir', str(art/'pep517'), str(ghost)],
                   capture_output=True, text=True)
assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
build_warnings = sorted({l.strip() for l in (r.stdout + r.stderr).splitlines() if 'warn' in l.lower() or 'LICENSE' in l})
# 2. Project's own release script (wheel, sdist, source zip, manifest)
r2 = subprocess.run([sys.executable, '-B', str(ghost/'scripts/build_distribution.py'), '--output', str(art/'release')],
                    capture_output=True, text=True)
assert r2.returncode == 0, r2.stdout[-3000:] + r2.stderr[-3000:]
# 3. plain git-archive source zip of tools/GHOST
gz = art/'git-archive-GHOST.zip'
if not fix:
    gz.write_bytes(subprocess.run(['git', '-C', str(repo), 'archive', '--format=zip', COMMIT, 'tools/GHOST'],
                                  check=True, capture_output=True).stdout)

def members(path):
    if path.suffix in ('.whl', '.zip'):
        with zipfile.ZipFile(path) as z:
            return {i.filename: z.read(i) for i in z.infolist() if not i.is_dir()}
    with tarfile.open(path) as t:
        return {m.name: t.extractfile(m).read() for m in t.getmembers() if m.isfile()}

tree = {p.relative_to(ghost).as_posix(): p.read_bytes() for p in ghost.rglob('*') if p.is_file()}
notices = sorted(n for n in tree if any(k in n.upper() for k in ('LICENSE', 'NOTICE', 'COPYING')))
vendored = {'ghost_backend/execution/thread_control/_threadpoolctl.py': 'ghost_backend/execution/thread_control/LICENSE-3.6.0.txt'}
report = dict(commit=COMMIT, fix_applied=fix, python=sys.version.split()[0], build_warnings=build_warnings,
              tree_files=len(tree), notices_in_tree={n: sha(tree[n]) for n in notices}, artifacts={})
for path in sorted(p for p in art.rglob('*') if p.suffix in ('.whl', '.zip', '.gz')):
    m = members(path)
    def strip(name):  # normalise to path relative to tools/GHOST
        for marker in ('tools/GHOST/', 'GHOST/'):
            if name.startswith(marker): return name[len(marker):]
        parts = name.split('/', 1)
        if path.suffix == '.gz' and len(parts) == 2: return parts[1]
        return name
    norm = {strip(k): v for k, v in m.items()}
    entry = dict(members=len(m), sha256=sha(path.read_bytes()))
    entry['notices'] = {n: ('identical' if norm.get(n) == tree[n] else 'DIFFERENT' if n in norm else 'MISSING') for n in notices}
    entry['vendored_code_without_notice'] = [c for c, n in vendored.items() if c in norm and norm.get(n) != tree[n]]
    entry['native_binaries'] = sorted(n for n in norm if n.endswith(('.so', '.dll')))
    missing = sorted(n for n in tree if n.startswith('ghost_backend/') and n not in norm)
    entry['ghost_backend_files_absent'] = len(missing)
    entry['absent_non_binary'] = [n for n in missing if not n.endswith(('.so', '.dll'))]
    entry['changed_vs_tree'] = sorted(n for n in norm if n in tree and norm[n] != tree[n])
    report['artifacts'][path.relative_to(art).as_posix()] = entry
out.write_text(json.dumps(report, indent=2) + '\n')
for k, v in report['artifacts'].items():
    print(k, v['members'], v['notices'], 'vendored w/o notice:', v['vendored_code_without_notice'], 'natives:', len(v['native_binaries']), 'absent non-binary:', len(v['absent_non_binary']))
