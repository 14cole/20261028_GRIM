#!/bin/bash
# Stage-instrumented Dense run at 23,936 unknowns with 20 s samples of process and cgroup memory and I/O.
#   GRIM_ROOT=<ed90b65> ./trace_24k.sh results/c_trace24k
out=$1; mkdir -p "$out"; here=$(cd "$(dirname "$0")" && pwd)
cg=/sys/fs/cgroup/memory$(grep ':memory:' /proc/self/cgroup | cut -d: -f3)
df -m "${TMPDIR:-/tmp}" | tail -1 > "$out/scratch_free_before.txt"
PYTHONPATH="$here" python3 "$here/timed_job.py" 8448 dense 360 4 "$out/s8448_a360_t4_dense.npz" > "$out/dense.out" 2> "$out/dense.err" &
pid=$!
echo "t_s rss_kb hwm_kb rchar wchar read_bytes write_bytes cg_usage cg_cache cg_rss cg_mapped_file cg_inactive_file cg_active_file pgmajfault psi_some_avg10" > "$out/samples.txt"
start=$(date +%s)
while kill -0 $pid 2>/dev/null; do
  s=/proc/$pid/status; io=/proc/$pid/io
  echo "$(( $(date +%s)-start )) $(awk '/VmRSS/{print $2}' $s) $(awk '/VmHWM/{print $2}' $s) $(awk '/^rchar/{print $2}' $io) $(awk '/^wchar/{print $2}' $io) $(awk '/^read_bytes/{print $2}' $io) $(awk '/^write_bytes/{print $2}' $io) $(cat $cg/memory.usage_in_bytes 2>/dev/null) $(awk '/^total_cache /{print $2}' $cg/memory.stat) $(awk '/^total_rss /{print $2}' $cg/memory.stat) $(awk '/^total_mapped_file /{print $2}' $cg/memory.stat) $(awk '/^total_inactive_file /{print $2}' $cg/memory.stat) $(awk '/^total_active_file /{print $2}' $cg/memory.stat) $(awk '/^pgmajfault /{print $2}' /proc/vmstat) $(awk '/some/{print $2}' /proc/pressure/memory 2>/dev/null)" >> "$out/samples.txt"
  sleep 20
done
wait $pid; echo "rc=$? wall=$(( $(date +%s)-start ))s" > "$out/status.txt"
