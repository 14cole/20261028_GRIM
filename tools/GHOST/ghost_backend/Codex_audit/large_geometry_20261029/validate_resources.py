"""Run focused resource regressions with isolated pytest plugins and saved evidence."""
import json
import os
from pathlib import Path
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT.parent),str(ROOT/'tests')]
os.environ.update(OPENBLAS_NUM_THREADS='4',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',
                  PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',QT_QPA_PLATFORM='offscreen')
os.chdir(ROOT)
import pytest


class Report:
    def __init__(self):self.rows=[]
    def pytest_runtest_logreport(self,report):
        if report.when=='call' or report.failed:
            row=dict(test=report.nodeid,phase=report.when,outcome=report.outcome,seconds=report.duration)
            if report.failed:row['failure']=str(report.longrepr)
            self.rows.append(row)
            (HERE/'validation_results.json').write_text(json.dumps(self.rows,indent=2),encoding='utf-8')


if __name__=='__main__':
    report=Report()
    files=['tests/test_hmatrix_resource_bounds.py','tests/test_hmatrix_product_resources.py',
           'tests/test_bounded_factor_workspaces.py','tests/test_solver_resource_recovery.py',
           'tests/test_compressed_memory.py','tests/test_factorization_audit_resources.py']
    code=pytest.main([*files,'-q','--tb=short','--rootdir='+str(ROOT),
        '--basetemp='+str(HERE/('validation_tmp_'+str(time.time_ns()))),
        '-p','no:cacheprovider','-o','faulthandler_timeout=60'],plugins=[report])
    summary=dict(exit_code=code,tests=len(report.rows),passed=sum(r['outcome']=='passed' for r in report.rows),
        files=files,note='Earlier plain pytest invocations did not return cleanly and were interrupted; this run isolates plugins and disables the cache provider.')
    (HERE/'validation_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary),flush=True)
    raise SystemExit(code)
