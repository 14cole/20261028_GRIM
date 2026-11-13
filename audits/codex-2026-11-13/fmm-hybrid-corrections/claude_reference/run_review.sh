#!/bin/bash
# one case per fresh process, memory-limited; appends to review.jsonl; skips cases already recorded
python3 - <<'PY'
import json, subprocess, os, sys
cases=json.load(open('cases.json')); done=set()
if os.path.exists('review.jsonl'):
    for l in open('review.jsonl'):
        try: done.add(json.loads(l).get('_key'))
        except Exception: pass
for c in cases:
    key=json.dumps(c,sort_keys=True)
    if key in done: continue
    p=subprocess.run('ulimit -v 10000000; timeout 1500 python3 review_checks.py %s %s' % (os.environ['GRIM_ROOT'], "'"+json.dumps(c)+"'"), shell=True, capture_output=True, text=True)
    line=[l for l in p.stdout.splitlines() if l.startswith('{')]
    r=json.loads(line[-1]) if line else dict(c, error='process failed: '+p.stderr[-300:])
    r['_key']=key; open('review.jsonl','a').write(json.dumps(r)+'\n')
PY
echo finished
