"""Run the reviewer regression matrix against the actual proposed source diff."""
import os,sys,tempfile,shutil,subprocess,ast,runpy,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST'))
from ghost_backend.compressed.hmatrix import BlockRow
original=BlockRow.values
with tempfile.TemporaryDirectory() as tmp:
    tmp=Path(tmp);rel=Path('tools/GHOST/ghost_backend/compressed/hmatrix.py')
    (tmp/rel).parent.mkdir(parents=True);shutil.copyfile(Path(os.environ['GRIM_ROOT'])/rel,tmp/rel)
    subprocess.run(['git','apply','--check',str(ROOT/'candidate-gather-v2.patch')],cwd=tmp,check=True)
    subprocess.run(['git','apply',str(ROOT/'candidate-gather-v2.patch')],cwd=tmp,check=True)
    tree=ast.parse((tmp/rel).read_text());cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='BlockRow')
    method=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='values')
    scope={'np':np};exec(compile(ast.Module(body=[method],type_ignores=[]),'actual-patched-values','exec'),scope)
    patched=scope['values']
    import gather_v2
    def install():BlockRow.values=patched;return original,patched
    gather_v2.install=install
    cwd=Path.cwd();os.chdir(tmp)
    try:runpy.run_path(str(ROOT/'claude/claude_gather_v2_tests.py'),run_name='__main__')
    finally:os.chdir(cwd)
    d=json.loads((tmp/'claude_gather_v2_tests.json').read_text())
    assert d['cases']==17700 and d['v2_mismatches']==0 and d['v1_mismatches']==3600
    d.update(actual_patch_applied_to_temporary_copy=True,production_unchanged=True)
    (ROOT/'actual-patch-check.json').write_text(json.dumps(d,indent=2))
