"""Execute the actual unapplied patch, then Claude's random checks unchanged."""
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
    tree=ast.parse((tmp/rel).read_text())
    cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='BlockRow')
    method=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='values')
    scope={'np':np};exec(compile(ast.Module(body=[method],type_ignores=[]),'patched-values','exec'),scope)
    patched=scope['values']
    import query_hook
    def install(*a,**kw):BlockRow.values=patched
    query_hook.install=install
    cwd=Path.cwd();os.chdir(tmp)
    try:runpy.run_path(str(ROOT/'claude/claude_gather_tests.py'),run_name='__main__')
    finally:os.chdir(cwd)
    d=json.loads((tmp/'claude_gather_tests.json').read_text())
    assert d['value_cases']==16401 and not d['mismatches']
    assert all(x['original']==x['patched']=='IndexError' for x in d['path_checks'])
    empty_checks=0
    for r,c in [(np.array([4]),np.array([],int)),(np.array([-5]),np.array([],int)),(np.array([],int),np.array([5]))]:
        row=BlockRow(0,0,4,[(0,5)],np.zeros((4,5),complex),None)
        for fn in (original,patched):
            try:fn(row,r,c)
            except IndexError:pass
            else:raise AssertionError('Expected IndexError')
        empty_checks+=1
    d.update(actual_patch_applied_to_temporary_copy=True,empty_invalid_selector_checks=empty_checks,production_unchanged=True)
    (ROOT/'v2-gather-tests.json').write_text(json.dumps(d,indent=2))
