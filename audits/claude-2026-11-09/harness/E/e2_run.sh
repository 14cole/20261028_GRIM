#!/bin/bash
# cross-backend matrix
N=${N:-1200}; F=${F:-10.0}
mkdir -p res
for c in pec ibc diel diel_res coat coat_thin two_pec two_ibc; do
 for b in lu hodlr tile hmat; do
  f=res/${c}_${b}_${N}_${F}.json
  [ -s $f ] && continue
  timeout 400 python e2_case.py $c $b $N $F 2>res/${c}_${b}_${N}_${F}.err | grep -a "^JSON" | cut -c5- > $f
  echo "$c $b done $(date +%T)"
 done
done
