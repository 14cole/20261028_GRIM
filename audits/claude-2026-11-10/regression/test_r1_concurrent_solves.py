"""R-1: overlapping in-process solves must not fail with a 0 GiB reservation."""
import threading
import time
from common import *
from ghost_backend.twod import solver as S
from ghost_backend.execution import memory_budget

small = scene([("b", 2, "2 1 0 0 0", circle(0.1, 68))])
reference = S.solve_monostatic_rcs_2d(small, [1.0], [0.0], geometry_units="meters", solver_method="direct")
ref = amp(reference["samples"], "VV")[0]


def run(results, index, method, geometry=small, **kw):
    try:
        r = S.solve_monostatic_rcs_2d(geometry, [1.0], [0.0], geometry_units="meters", solver_method=method, **kw)
        results[index] = amp(r["samples"], "VV")[0]
    except BaseException as error:  # noqa: BLE001
        results[index] = error


for label, methods in (("3 x direct", ["direct"] * 3), ("4 x auto", ["auto"] * 4),
                       ("mixed direct/auto", ["direct", "auto", "direct", "auto"])):
    results = {}
    threads = [threading.Thread(target=run, args=(results, i, m)) for i, m in enumerate(methods)]
    [t.start() for t in threads]
    [t.join(300) for t in threads]
    alive = any(t.is_alive() for t in threads)
    errors = [repr(v)[:120] for v in results.values() if isinstance(v, BaseException)]
    ok = not alive and not errors and all(abs(v - ref) <= 1e-9 * abs(ref) for v in results.values())
    check(label + " all succeed with the serial answer", ok, errors or ("deadlock" if alive else ""))

# A waiting solve honours its abort event.
big = scene([("b", 2, "2 1 0 0 0", circle(0.1, 1500))])
results = {}
event = threading.Event()
first = threading.Thread(target=run, args=(results, "first", "direct", big))
first.start()
time.sleep(1.0)
waiter = threading.Thread(target=run, args=(results, "waiter", "direct"), kwargs=dict(abort_event=event))
waiter.start()
time.sleep(0.5)
event.set()
waiter.join(20)
check("waiting solve aborts promptly", isinstance(results.get("waiter"), InterruptedError), repr(results.get("waiter"))[:120])
first.join(300)
check("first solve unaffected by the aborted waiter", isinstance(results.get("first"), complex))
with memory_budget._LOCK:
    check("no request left enrolled", len(list(memory_budget._REQUESTS)) == 0)
after = S.solve_monostatic_rcs_2d(small, [1.0], [0.0], geometry_units="meters", solver_method="direct")
check("next solve after all of that is correct", abs(amp(after["samples"], "VV")[0] - ref) <= 1e-12 * abs(ref))

# A failing solve releases its turn.
bad = scene([("s", 2, "2 -20 0 0 0", rows([(-0.05, 0.0), (0.05, 0.0)]))])
check("failed solve raises", *raises(lambda: S.solve_monostatic_rcs_2d(bad, [1.0], [0.0], geometry_units="meters"), ValueError))
with memory_budget._LOCK:
    check("failed solve left no reservation", len(list(memory_budget._REQUESTS)) == 0)
finish()
