#!/bin/bash
while pgrep -f fvr.sh >/dev/null; do sleep 5; done
echo "== kill test"; timeout 400 python3 kill1.py 2>&1 | tail -3
for w in 1 auto; do echo "== SWEEP workers=$w a=0.5 f=6 nf=4 (N~1280, default profile)"; timeout 900 python3 mon.py python3 sweep.py $w 0.5 6 4 2>&1 | tail -2; done
for w in 1 auto; do echo "== SWEEP workers=$w a=1.0 f=12 nf=2 (N~5120, default profile)"; timeout 1500 python3 mon.py python3 sweep.py $w 1.0 12 2 2>&1 | tail -2; done
