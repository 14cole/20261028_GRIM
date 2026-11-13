#!/bin/bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
for spec in '"n":2048,"k":[40,0]' '"n":4096,"k":[40,0]' '"n":2048,"k":[40,-0.8]' '"n":2048,"k":[160,0]' '"n":1024,"k":[6,0]'; do
 for mode in moment stream; do
  s="{$spec,\"mode\":\"$mode\"}"; key=$(echo "$s" | md5sum | cut -c1-12)
  grep -q "\"_key\": \"$key\"" moment.jsonl 2>/dev/null && continue
  out=$( (ulimit -v 10000000; timeout 3000 python3 moment_benchmark.py "$s") 2>moment_last.err | tail -1)
  [ -z "$out" ] && out="{\"error\": \"failed or timed out\", \"spec\": $s}"
  echo "${out%\}}, \"_key\": \"$key\"}" >> moment.jsonl
 done
done
