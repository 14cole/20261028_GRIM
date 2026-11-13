#!/bin/bash
# resumable: one case per process
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
while read -r spec; do
  key=$(echo "$spec" | md5sum | cut -c1-12)
  grep -q "\"_key\": \"$key\"" precond.jsonl 2>/dev/null && continue
  out=$( (ulimit -v 10000000; timeout 2400 python3 precond_study.py "$spec") 2>precond_last.err | tail -1)
  [ -z "$out" ] && out="{\"error\": \"failed or timed out\", \"spec\": $spec}"
  echo "${out%\}}, \"_key\": \"$key\"}" >> precond.jsonl
done <<'CASES'
{"n":512,"k":40,"kind":"TE","restart":400,"cycles":2}
{"n":512,"k":40,"kind":"TM","restart":400,"cycles":2}
{"n":1024,"k":40,"kind":"TE","restart":400,"cycles":2}
{"n":1024,"k":40,"kind":"TM","restart":400,"cycles":2}
{"n":1024,"k":80,"kind":"TE","restart":400,"cycles":2}
{"n":2048,"k":40,"kind":"TE","restart":400,"cycles":2}
{"n":2048,"k":80,"kind":"TE","restart":400,"cycles":2}
{"n":2048,"k":80,"kind":"TM","restart":400,"cycles":2}
{"n":1024,"k":40,"kind":"TE","restart":400,"cycles":2,"eps":[3.0,-1.0]}
{"n":1024,"k":40,"kind":"TE","restart":400,"cycles":2,"eps":[12.0,-0.1]}
CASES
