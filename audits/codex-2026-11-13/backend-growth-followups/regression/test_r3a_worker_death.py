"""R-3a: a frequency worker killed by the OS must not abort the sweep."""
import os
import signal
import threading
import time
from common import *

if __name__ == "__main__":
    import psutil
    from ghost_backend.twod import solver as S
    from ghost_backend.execution.options import automatic_run, execution_scope
    from ghost_backend.execution.fresh_sweep import run_fresh

    profile = automatic_run("monostatic")
    options = profile["execution_options"]
    g = scene([("b", 2, "2 0 0 0 0", circle(0.5, 256))])
    freqs = [6.0, 6.06, 6.12, 6.18]
    angles = [float(a) for a in np.linspace(0, 180, 19)]
    kw = dict(geometry_snapshot=g, frequencies_ghz=freqs, elevations_deg=angles, geometry_units="meters",
              solver_method=profile["solver_method"], max_panels=100000)
    me = psutil.Process()
    killed = []

    def killer():
        while not killed:
            try:
                kids = [c for c in me.children(recursive=True) if "spawn_main" in " ".join(c.cmdline())]
                busy = [c for c in kids if c.cpu_times().user > 2.5]
                if busy:
                    os.kill(busy[0].pid, signal.SIGKILL)
                    killed.append(busy[0].pid)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.1)

    threading.Thread(target=killer, daemon=True).start()
    try:
        with execution_scope(options, limit_blas=True):
            swept = run_fresh(S.solve_monostatic_rcs_2d_survey, kw, options, "double", False, frequency_workers=2)
        error = None
    except BaseException as exc:  # noqa: BLE001
        swept, error = None, exc
    check("a worker was killed during the sweep", bool(killed))
    check("sweep completed after the worker died", error is None, repr(error)[:160])
    if swept is not None:
        execution = swept["metadata"]["frequency_execution"]
        check("lost units are reported", execution.get("units_lost_to_worker_failure", 0) >= 1, execution)
        check("every frequency and angle is present", len(swept["samples"]) == 2 * len(freqs) * len(angles))
        killed.append(0)  # stop the killer before the reference run
        with execution_scope(options, limit_blas=True):
            serial = run_fresh(S.solve_monostatic_rcs_2d_survey, kw, options, "double", False, frequency_workers=1)
        worst = max(np.max(np.abs(amp(swept["samples"], pol) - amp(serial["samples"], pol)) / np.max(np.abs(amp(serial["samples"], pol))))
                    for pol in ("VV", "HH"))
        check("recovered sweep equals the sequential sweep", worst < 1e-9, "max relative difference {:.2e}".format(worst))
        order = [(s["frequency_ghz"], s["theta_inc_deg"], s["polarization"]) for s in swept["samples"]]
        check("sample order equals the sequential order", order == [(s["frequency_ghz"], s["theta_inc_deg"], s["polarization"]) for s in serial["samples"]])
    # --- pool breaks before a submission (Codex implementation review, finding 2) ---
    # The executor's own first worker is killed just before the second unit is
    # submitted, and the executor is given time to notice, so submit() itself
    # raises BrokenProcessPool.
    from concurrent.futures import ProcessPoolExecutor
    from ghost_backend.execution import frequency_sweep as F
    killed_early = []

    class KillBeforeSecondSubmit(ProcessPoolExecutor):
        calls = 0

        def submit(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 2:
                process = next(iter(self._processes.values()))
                os.kill(process.pid, signal.SIGKILL)
                killed_early.append(process.pid)
                deadline = time.monotonic() + 5
                while not self._broken and time.monotonic() < deadline:
                    time.sleep(0.01)
            return super().submit(*args, **kwargs)

    original_executor = F.ProcessPoolExecutor
    F.ProcessPoolExecutor = KillBeforeSecondSubmit
    try:
        with execution_scope(options, limit_blas=True):
            early = run_fresh(S.solve_monostatic_rcs_2d_survey, kw, options, "double", False, frequency_workers=2)
        error = None
    except BaseException as exc:  # noqa: BLE001
        early, error = None, exc
    finally:
        F.ProcessPoolExecutor = original_executor
    check("a worker was killed before the second submission", bool(killed_early))
    check("sweep completed although submit() found the pool broken", error is None, repr(error)[:160])
    if early is not None:
        execution = early["metadata"]["frequency_execution"]
        check("units lost at submission are reported", execution.get("units_lost_to_worker_failure", 0) >= 1, execution)
        worst = max(np.max(np.abs(amp(early["samples"], pol) - amp(serial["samples"], pol))) / np.max(np.abs(amp(serial["samples"], pol)))
                    for pol in ("VV", "HH"))
        check("sweep recovered at submission equals the sequential sweep", worst < 1e-9, "max relative difference {:.2e}".format(worst))
        check("its sample order equals the sequential order",
              [(s["frequency_ghz"], s["theta_inc_deg"], s["polarization"]) for s in early["samples"]]
              == [(s["frequency_ghz"], s["theta_inc_deg"], s["polarization"]) for s in serial["samples"]])
    leftovers = [c for c in me.children(recursive=True) if "spawn_main" in " ".join(c.cmdline())]
    check("no worker process left behind", not leftovers, [c.pid for c in leftovers])
    finish()
