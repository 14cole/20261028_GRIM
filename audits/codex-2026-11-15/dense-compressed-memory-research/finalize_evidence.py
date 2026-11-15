"""Run after the numerical suites; preserve and verify all evidence serially."""
import os,sys,subprocess,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
def run(script,*args,extra=None):
    print('PHASE',script,flush=True)
    subprocess.run([sys.executable,str(HERE/script),*map(str,args)],env=dict(env,**(extra or {})),check=True)
run('pack_evidence.py')
run('unpack_evidence.py',HERE/'restored')
run('verify_evidence.py',HERE/'restored')
run('analyze.py',extra={'RESULTS_DIR':str(HERE/'restored/results'),'ANALYSIS_OUT':str(HERE/'replayed-analysis.json')})
assert json.loads((HERE/'analysis.json').read_text())==json.loads((HERE/'replayed-analysis.json').read_text())
(HERE/'analysis-replay-verification.json').write_text(json.dumps({'exact_json_match':True,'evidence':'lossless restored-array replay; not fresh solves'},indent=2))
run('build_handoff.py')
print('Evidence verified; ready for review and publication.',flush=True)
