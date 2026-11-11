"""Boundary, override, concurrency and restoration checks for the new policies."""
import json,os,sys,threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
sys.path.insert(0,str(Path(sys.argv[1])/'tools/GHOST'))
import numpy as np,scipy.linalg
from ghost_backend.execution.options import (execution_scope,linear_algebra_threads,factor_blas_threads,
    automatic_options,automatic_policy_requested,validate_for_run)
from ghost_backend.execution.policy import rank_automatic
from ghost_backend.linalg.hierarchical import automatic_hierarchical,automatic_twod_hierarchical
from ghost_backend.compressed.hmatrix import minimum_unknowns
from ghost_backend.execution.thread_control import threadpool_info
checks=[]
def check(name,value):
    assert value,name
    checks.append(name)
def pools():return [x['num_threads'] for x in threadpool_info() if x.get('user_api')=='blas']
c={'dense':dict(cost=10.,peak_gb=2.),'compressed':dict(cost=1.,peak_gb=1.)}
check('small fitting systems prefer dense',rank_automatic(c,4.,9999)[0]=='dense')
check('boundary prefers compressed',rank_automatic(c,4.,10000)[0]=='compressed')
check('small systems cannot bypass RAM',rank_automatic(c,1.5,9999)==['compressed'])
check('large systems keep admitted dense fallback',rank_automatic(c,4.,10000)==['compressed','dense'])
try:rank_automatic(c,.5,100)
except MemoryError:check('neither backend fits rejects',True)
else:raise AssertionError('RAM admission bypassed')
with patch.dict(os.environ,{},clear=False):
    os.environ.pop('GHOST_HIERARCHICAL_MIN_UNKNOWNS',None)
    os.environ.pop('GHOST_HMATRIX_MIN_UNKNOWNS',None)
    check('BoR keeps large default HODLR policy',automatic_hierarchical(10000))
    check('2D large dense defaults to LU',not automatic_twod_hierarchical(10000))
    check('explicit compressed keeps representation threshold',minimum_unknowns()==8192)
    with execution_scope(automatic_options()):
        check('automatic compressed can use H-matrix below old threshold',minimum_unknowns()==1024)
        with execution_scope(dict(automatic_options(),factorization='dense')):
            check('candidate scope retains automatic policy',automatic_policy_requested())
    check('automatic policy restored after scope',not automatic_policy_requested())
    with patch.dict(os.environ,{'GHOST_HIERARCHICAL_MIN_UNKNOWNS':'1'}):
        check('explicit HODLR threshold retained',automatic_twod_hierarchical(2))
    with patch.dict(os.environ,{'GHOST_HMATRIX_MIN_UNKNOWNS':'0'}),execution_scope(automatic_options()):
        check('explicit tile override retained',minimum_unknowns()==0)
class H:
    automatic_blas_threads=1
    @factor_blas_threads
    def evaluate(self,fail=False):
        value=pools()
        if fail:raise InterruptedError('cancelled')
        return value
h=H()
with execution_scope(dict(blas_threads='auto')),linear_algebra_threads(4000):
    before=pools();check('automatic H-matrix uses one BLAS thread',all(x==1 for x in h.evaluate()))
    check('BLAS restored on success',pools()==before)
    try:h.evaluate(True)
    except InterruptedError:pass
    check('BLAS restored on cancellation',pools()==before)
with execution_scope(dict(blas_threads=2)),linear_algebra_threads(4000):
    check('explicit thread request retained',all(x==2 for x in h.evaluate()))
barrier=threading.Barrier(2)
def concurrent(setting):
    barrier.wait()
    for _ in range(5):
        with execution_scope(dict(blas_threads=setting)),linear_algebra_threads(4000):
            expected=1 if setting=='auto' else 2
            assert all(x==expected for x in h.evaluate())
    return True
with ThreadPoolExecutor(2) as pool:
    futures=[pool.submit(concurrent,s) for s in ('auto',2)]
    check('concurrent requests preserve limits',all(f.result(timeout=15) for f in futures))
from ghost_backend.runs.batch import apply_batch_choices,combine_channels
records=[dict(unit='small',automatic_unknowns=4000,backend_candidates=c),dict(unit='large',automatic_unknowns=12000,backend_candidates=c)]
_,chosen,_=apply_batch_choices(records,4,2,4.,automatic_options())
check('HPC automatic policy matches size rule',chosen['small']['selected']=='dense' and chosen['large']['selected']=='compressed')
check('HPC retry cannot exceed reservation',chosen['large']['retry_order']==[])
for mode in ('automatic','compressed','dense','adaptive','hierarchical','auto'):
    check('saved mode accepted '+mode,validate_for_run(dict(factorization=mode),method='auto')['factorization']==mode)
Path(__file__).with_name('policy-results.json').write_text(json.dumps(dict(passed=len(checks),checks=checks),indent=2)+'\n')
print('PASS',len(checks),'policy/thread checks')
