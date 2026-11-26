#!/bin/sh
# Real nested-cgroup check (cgroup v1 memory controller, needs root).
# Usage: run_real_cgroup.sh RELEASE_GHOST_ROOT FIXED_GHOST_ROOT OUTDIR
# Creates <own memory cgroup>/ghost-audit-probe (limit 1 GiB) and
# .../ghost-audit-probe/worker (no limit of its own), runs the probe from a
# short-lived process inside each, then removes both.  No large allocation.
set -u
REL=$1; FIX=$2; OUT=$3; HERE=$(dirname "$0"); mkdir -p "$OUT"
OWN=$(awk -F: '$2 ~ /(^|,)memory(,|$)/ {print $3}' /proc/self/cgroup)
BASE=/sys/fs/cgroup/memory$OWN
T=$BASE/ghost-audit-probe
mkdir -p "$T/worker" || exit 1
echo 1073741824 > "$T/memory.limit_in_bytes" || exit 1
inside() { # cgroup-dir, command...
  d=$1; shift; sh -c 'echo $$ > "$0/cgroup.procs" && exec "$@"' "$d" "$@"; }
rc=0
for v in release fixed; do
  if [ $v = release ]; then G=$REL; A=""; else G=$FIX; A=--assert-correct; fi
  python3 "$HERE/real_probe.py" "$G" "own group (container's nested group, no child)" $A > "$OUT/$v-own.json" || { echo "$v own: assertion failed"; rc=1; }
  inside "$T" python3 "$HERE/real_probe.py" "$G" "child with 1 GiB limit" $A > "$OUT/$v-child-1gib.json" || { echo "$v child: assertion failed"; rc=1; }
  inside "$T/worker" python3 "$HERE/real_probe.py" "$G" "unlimited grandchild under 1 GiB ancestor" $A > "$OUT/$v-finite-ancestor.json" || { echo "$v ancestor: assertion failed"; rc=1; }
  # Mount rooted below the global hierarchy: private mount namespace with the
  # 1 GiB group bind-mounted over the conventional v1 path.
  unshare -m sh -c 'mount --bind "$0" /sys/fs/cgroup/memory && echo $$ > /sys/fs/cgroup/memory/worker/cgroup.procs && exec "$@"' "$T" \
    python3 "$HERE/real_probe.py" "$G" "mount rooted at the 1 GiB group; process in its unlimited child" $A > "$OUT/$v-rooted-mount.json" || { echo "$v rooted mount: failed"; rc=1; }
  # Same, but the mount is rooted at the container's own group and the 1 GiB
  # limit sits one level below the mount root.
  unshare -m sh -c 'mount --bind "$0" /sys/fs/cgroup/memory && echo $$ > /sys/fs/cgroup/memory/ghost-audit-probe/worker/cgroup.procs && exec "$@"' "$BASE" \
    python3 "$HERE/real_probe.py" "$G" "mount rooted at own group; 1 GiB limit below the mount root" $A > "$OUT/$v-rooted-mount-limit-below.json" || { echo "$v rooted mount (limit below): failed"; rc=1; }
done
rmdir "$T/worker" "$T"
exit $rc
