#!/bin/sh
python3 - <<'PY'
import json,subprocess,sys,os
for r in json.load(open('claude_cancel_suite.json')):
    r=dict(r,out='out/'+r['name']);print('START',r['name'],flush=True)
    with open(r['out']+'.log','w') as o:rc=subprocess.run([sys.executable,'-W','ignore','claude_cancel.py',json.dumps(r)],stdout=o,stderr=subprocess.STDOUT).returncode
    print('END',r['name'],rc,flush=True)
PY
