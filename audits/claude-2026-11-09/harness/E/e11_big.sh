#!/bin/bash
mkdir -p big
for b in lu hodlr_auto hmat; do
  E_NANG=91 E_OPTS="blas_threads=1" timeout 900 python e2_case.py pec $b 8192 300.0 2>big/pec_$b.err | grep -a "^JSON" | cut -c5- > big/pec_$b.json
  echo "$b done $(date +%T)"
done
