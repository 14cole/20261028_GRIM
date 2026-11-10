#!/bin/bash
# forecast vs reality; BT=1 to limit load sensitivity (memory is unaffected by BLAS thread count apart from small per-thread buffers)
for cfg in "0.5 6 adaptive" "1.0 6 dense" "1.0 6 compressed" "1.0 12 dense" "1.0 12 compressed" "1.2 12 dense" "1.2 12 compressed" "2.0 12 compressed" "2.0 12 dense"; do
  echo "CFG $cfg"; BT=1 timeout 600 python3 mon.py python3 run2d.py $cfg 181 2>&1 | tail -2
done
