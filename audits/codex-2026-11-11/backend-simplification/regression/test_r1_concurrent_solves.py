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
# --- lock order (Codex implementation review, finding 1) ---------------------
# Request A holds the memory reservation and has not yet needed the BLAS lock.
# Thread B holds the BLAS lock through an outer execution_scope and starts a
# public solve.  B must not wait for A (A needs B's lock): neither may hang.
from ghost_backend.execution import options as O


def mixed_scope(expect_b_error):
    reserved, blas_held = threading.Event(), threading.Event()
    original = memory_budget.MemoryBudget.stable
    paused = [False]
    out = {}

    def gated(self):
        value = original(self)
        if threading.current_thread().name == "request-A" and not paused[0]:
            paused[0] = True
            reserved.set()
            blas_held.wait(10)      # hold the reservation until B owns the BLAS lock
        return value

    def a():
        try:
            with O.execution_scope({}, limit_blas=False):
                r = S.solve_monostatic_rcs_2d(small, [1.0], [0.0], geometry_units="meters", solver_method="direct")
            out["A"] = amp(r["samples"], "VV")[0]
        except BaseException as error:  # noqa: BLE001
            out["A"] = error

    def b():
        try:
            reserved.wait(10)
            with O.execution_scope({}, limit_blas=True):
                out["B_held"] = O.blas_lock_held()
                blas_held.set()
                if expect_b_error == "raise inside":
                    raise RuntimeError("caller error while holding the BLAS lock")
                r = S.solve_monostatic_rcs_2d(small, [1.0], [0.0], geometry_units="meters", solver_method="direct")
            out["B"] = amp(r["samples"], "VV")[0]
        except BaseException as error:  # noqa: BLE001
            out["B"] = error
        finally:
            blas_held.set()

    memory_budget.MemoryBudget.stable = gated
    try:
        ta = threading.Thread(target=a, name="request-A", daemon=True)
        tb = threading.Thread(target=b, name="request-B", daemon=True)
        ta.start(); tb.start()
        ta.join(60); tb.join(60)
        out["alive"] = [t.name for t in (ta, tb) if t.is_alive()]
    finally:
        memory_budget.MemoryBudget.stable = original
    return out


out = mixed_scope(None)
check("mixed scopes: neither thread hangs", out["alive"] == [], out["alive"])
check("mixed scopes: B really held the BLAS lock", out.get("B_held") is True)
check("mixed scopes: the reservation holder completes with the serial answer",
      isinstance(out.get("A"), complex) and abs(out["A"] - ref) <= 1e-12 * abs(ref), repr(out.get("A"))[:120])
b_error = out.get("B")
check("mixed scopes: the lock holder is refused at once with the cause named",
      isinstance(b_error, MemoryError) and "holds the memory reservation" in str(b_error) and "BLAS lock" in str(b_error),
      repr(b_error)[:160])
check("blas_lock_held is false outside any scope", not O.blas_lock_held())
with memory_budget._LOCK:
    check("mixed scopes: no request left enrolled", len(list(memory_budget._REQUESTS)) == 0)
out = mixed_scope("raise inside")
check("exception inside the outer scope releases the BLAS lock and the reservation",
      out["alive"] == [] and isinstance(out.get("A"), complex) and isinstance(out.get("B"), RuntimeError) and not O.blas_lock_held())
with O.execution_scope({}, limit_blas=True):
    held = O.blas_lock_held()
    r = S.solve_monostatic_rcs_2d(small, [1.0], [0.0], geometry_units="meters", solver_method="direct")
check("a solve inside an outer BLAS scope with no competitor is unaffected",
      held and abs(amp(r["samples"], "VV")[0] - ref) <= 1e-12 * abs(ref) and not O.blas_lock_held())
after = S.solve_monostatic_rcs_2d(small, [1.0], [0.0], geometry_units="meters", solver_method="direct")
check("next solve after the mixed-scope cases is correct", abs(amp(after["samples"], "VV")[0] - ref) <= 1e-12 * abs(ref))
finish()
