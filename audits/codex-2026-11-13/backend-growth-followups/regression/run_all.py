"""Run every regression script in a fresh interpreter and summarise."""
import glob
import os
import subprocess
import sys
import time

here = os.path.dirname(os.path.abspath(__file__))
failed = []
for path in sorted(glob.glob(os.path.join(here, "test_*.py"))):
    start = time.perf_counter()
    done = subprocess.run([sys.executable, path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    lines = done.stdout.splitlines()
    passes = sum(line.startswith("PASS ") for line in lines)
    fails = [line for line in lines if line.startswith("FAIL ")]
    ok = done.returncode == 0 and not fails
    print("{} {:<40} {:>3} passed, {} failed, {:.0f} s".format("ok  " if ok else "FAIL", os.path.basename(path), passes, len(fails),
                                                            time.perf_counter() - start), flush=True)
    for line in fails:
        print("     " + line[:200])
    if done.returncode and not fails:
        print("     exit code {}: {}".format(done.returncode, lines[-1][:200] if lines else ""))
    if not ok:
        failed.append(path)
print("{} script(s) failed".format(len(failed)))
sys.exit(1 if failed else 0)
