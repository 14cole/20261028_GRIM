"""Verify shipped Qt result presentation in a clean process for each provided checkout.

python verify_display.py CHECKOUT full|large OUT.json
Use QT_QPA_PLATFORM=offscreen on a headless machine.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
import gc
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import threading
import time
from unittest.mock import patch
import weakref

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "ghost-display-audit-mpl"))
import numpy as np
import psutil
import PySide6
from PySide6.QtWidgets import QApplication

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("checkout", type=Path)
parser.add_argument("case", choices=("full", "large"))
parser.add_argument("output", type=Path)
parser.add_argument("--limit-bytes", type=int, help="override the candidate display-column budget for fallback testing")
args = parser.parse_args()
checkout = args.checkout.resolve()
sys.path[:0] = [str(checkout), str(checkout / "tools/GHOST")]
from ghost_backend.execution.recovery import RecoveryRun
from ghost_backend.geometry.io import build_geometry_snapshot, parse_geometry
from ghost_backend.twod.samples import SampleTable, merge_tables
from ghost_backend.ui import solver, result_table

if args.limit_bytes is not None:
    assert hasattr(result_table, "_DISPLAY_COLUMN_LIMIT_BYTES")
    result_table._DISPLAY_COLUMN_LIMIT_BYTES = args.limit_bytes

snapshot = build_geometry_snapshot(*parse_geometry((checkout / "airfoil.geo").read_text()))
app = QApplication.instance() or QApplication([])
tab = solver.SolverTab()
large = args.case == "large"
requested = np.random.default_rng(7).permutation(np.linspace(3, 14.7, 53)).tolist() if large else [4., 1., 6., 2., 7., 3., 5.]  # large case changed from Codex: shuffled order, 53 frequencies
angles = np.linspace(-135, 135, 541) if large else np.array([42., -70., -3., 169., 97., -121., 14., 8., 83., 0., 26.])  # large case changed from Codex: 541 angles
cases = {}


def synthetic_plane(frequency):
    by_pol = {}
    for index, label in enumerate(("VV", "HH")):
        phase = .04 * frequency + np.deg2rad(angles) * (index + 1)
        amplitude = (1.5 + .6 * index + .85 * np.cos(phase)) * np.exp(1j * phase)
        linear = abs(amplitude) ** 2 / (8 * np.pi * frequency * 1e9 / 299792458.)
        columns = np.column_stack([np.full(len(angles), frequency), angles, angles, linear,
                                   10 * np.log10(linear), amplitude.real, amplitude.imag,
                                   np.angle(amplitude, deg=True), np.full(len(angles), 2e-12)])
        by_pol[label] = dict(samples=SampleTable(columns))
    channels, samples = merge_tables(by_pol)
    return dict(samples=samples, co_solved_samples=channels, solver="2d_monostatic_rcs",
                scattering_mode="monostatic", polarizations=["VV", "HH"],
                polarization_mapping={"VV": "TE", "HH": "TM"}, amplitude_convention="fixture",
                rcs_log_unit="dBke", rcs_linear_quantity="sigma_2d", metadata=dict(
                    mesh_convergence_certified=False, geometry_units_in="meters", panel_count=12))


@contextmanager
def measure_loads(record):
    frequencies = []
    original_load = RecoveryRun.load

    def tracked(owner, f):
        frequencies.append(f)
        return original_load(owner, f)

    process = psutil.Process()
    stop = threading.Event()
    base = process.memory_info().rss
    peak = [base]

    def sample():
        while not stop.wait(.004):
            peak[0] = max(peak[0], process.memory_info().rss)

    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    with patch.object(RecoveryRun, "load", tracked):
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            peak[0] = max(peak[0], process.memory_info().rss)
            stop.set()
            thread.join()
            record.update(seconds=elapsed, verified_frequency_loads=len(frequencies),
                          distinct_frequencies=len(set(frequencies)),
                          loads_per_frequency=sorted(set(Counter(frequencies).values())),
                          incremental_peak_rss_mib=(peak[0] - base) / 2**20)
            if len(frequencies) <= 15:
                record["read_order_ghz"] = frequencies


def digest(payload):
    return hashlib.sha256(json.dumps(payload, allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def capture_visible_values():
    model = tab.result_table_model
    headings = list(model.headers)
    # Incrementally hash each complete row, including labels and the displayed precision.
    cells = hashlib.sha256()
    for r in range(model.rowCount()):
        formatted = [model.data(model.index(r, c)) for c in range(model.columnCount())]
        cells.update(json.dumps(formatted, ensure_ascii=False, separators=(",", ":")).encode() + b"\n")
    ax = tab.canvas.ax
    lines = [(line.get_label(), line.get_xdata().tolist(), line.get_ydata().tolist()) for line in ax.lines]
    return dict(headers=headings, table_sha256=cells.hexdigest(), curves_sha256=digest(lines),
                rows=model.rowCount(), cells=model.rowCount() * model.columnCount(),
                curves=len(lines), plot_labels=[ax.get_title(), ax.get_xlabel(), ax.get_ylabel()])


def finished(result):
    histories = []
    tab.chk_export_after_solve.setChecked(True)
    tab.edit_output.setText(str(root / "capture.grim"))
    def capture(result, output_path, *, source_path, history: str):
        histories.append(history)
        return [output_path]
    with patch.object(tab, "_export_result_files", capture):
        tab._on_solver_finished(result, "")
    return histories


def run_case(key, completed, recovered=False):
    run = RecoveryRun.create(root / key, dict(geometry_snapshot=snapshot, geometry_units="meters",
        frequencies_ghz=requested, elevations_deg=angles.tolist()), {}, "double", False)
    for frequency in reversed(completed):
        run.save(frequency, synthetic_plane(frequency))
    result = run.result()
    metrics = {}
    with measure_loads(metrics):
        if recovered:
            with patch.object(solver.QFileDialog, "getOpenFileName",
                              return_value=(str(run.directory / "run.json"), "")):
                tab._recover_completed_run()
            history = []
        else:
            history = finished(result)
        tab.canvas.draw()
    checked = {}
    with measure_loads(checked):
        values = capture_visible_values()
    assert values["rows"] == len(completed) * len(angles) * 2
    assert values["curves"] == len(completed) * 2
    state = dict(status=tab.lbl_status.text().replace(str(run.directory), "<run>"),
                 history=history, missing=result["metadata"]["run_recovery"]["remaining_frequencies_ghz"])
    repeated = {}
    if not large:
        with measure_loads(repeated):
            tab._select_result_view("rcs")
            tab.canvas.draw()
        assert capture_visible_values() == values
    cases[key] = dict(presentation=metrics, all_cells=checked, repeated_view=repeated, values=values, state=state)
    return run, weakref.ref(tab.last_result["samples"].reader)


with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    run, old_reader = run_case("complete", requested)
    if not large:
        partial, _ = run_case("partial_recover_dialog", [4., 6., 7., 5.], recovered=True)
        gc.collect()
        cases["complete"]["reader_released_after_replacement"] = old_reader() is None
        assert old_reader() is None
        # Corruption after the manifest/header checks, before first access to this result.
        damaged = run.result()
        reader = run.result()["samples"].reader
        record = run.store._path(7.)
        record.write_bytes(record.read_bytes() + b"damage")
        assert reader.read(4.) is not None
        try:
            reader.read(7.)
        except OSError:
            pass
        else:
            raise AssertionError("Corrupted record was accepted")
        valid_after_failed_read = reader.read(4.) is not None
        errors = []
        with (patch.object(solver.QMessageBox, "warning", side_effect=lambda *v: errors.append(str(v[-1]))),
              patch.object(solver.QMessageBox, "critical", side_effect=lambda *v: errors.append(str(v[-1])))):
            try:
                finished(damaged)
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
        assert any("corrupt" in msg.lower() for msg in errors), errors
        cases["corrupt_after_index"] = {"messages": errors, "blocked": True,
            "previous_result_kept": tab.last_result is not damaged,
            "previous_valid_record_readable_after_error": valid_after_failed_read}

        # Exercise non-disk result variants on the same tab, including missing fields and
        # per-row polarizations. They present through the same completion slot.
        for mode in ("bor", "bistatic"):
            data = []
            for f, label, inc, obs, linear in [(2., "HH", 45., 20., 1.), (1., "VV", 12., 10., 0.),
                                               (2., "HH", 20., -30., .2), (1., "VV", 12., -15., 1.25)]:
                data.append(dict(frequency_ghz=f, polarization=label, theta_inc_deg=inc,
                                 theta_scat_deg=obs, rcs_linear=linear))
            result = dict(samples=data, metadata=dict(geometry_units_in="meters"))
            if mode == "bor":
                result.update(solver="bor_mom_rcs", rcs_linear_quantity="sigma_3d")
            else:
                result.update(solver="2d_bistatic_rcs", scattering_mode="bistatic")
            history = finished(result)
            cases[mode + "_plain_list"] = dict(values=capture_visible_values(), status=tab.lbl_status.text(),
                                                history=history)
        # Replacing a generic result's sample list in place must refresh the table and plot
        # on redisplay even though the containing dict is still the active result object.
        same = {"samples": [dict(frequency_ghz=1., polarization="VV", theta_inc_deg=0.,
                                theta_scat_deg=0., rcs_linear=.1)]}
        finished(same)
        same["samples"] = [dict(frequency_ghz=2., polarization="HH", theta_inc_deg=5.,
                                theta_scat_deg=5., rcs_linear=1.5),
                           dict(frequency_ghz=1., polarization="VV", theta_inc_deg=15.,
                                theta_scat_deg=15., rcs_linear=.2)]
        tab._select_result_view("rcs")
        refreshed = capture_visible_values()
        assert refreshed["rows"] == 2 and refreshed["curves"] == 2
        cases["generic_in_place_refresh"] = dict(values=refreshed)

        # Exercise the checkpoint codec for the two BoR ordering conventions and bistatic
        # grouping. These display-only fixtures bypass the per-frequency feature export step.
        for disk_shape in ("bor_requested_order", "bor_expanded_order", "bistatic", "extension"):
            frequencies = [2., 3., 1.]
            bor = disk_shape.startswith("bor")
            dataset = RecoveryRun.create(root / disk_shape, dict(geometry_snapshot=snapshot,
                geometry_units="meters", frequencies_ghz=frequencies, elevations_deg=angles.tolist()),
                {}, "double", False, solver_kind="bor" if bor else "2d")
            for frequency in reversed(frequencies):
                plane = synthetic_plane(frequency)
                if bor:
                    plane.update(solver="bor_mom_rcs", rcs_linear_quantity="sigma_3d")
                    plane["metadata"]["expanded_to_360"] = disk_shape == "bor_expanded_order"
                if disk_shape in ("bistatic", "extension"):
                    plane.update(solver="2d_bistatic_rcs", scattering_mode="bistatic")
                    # Deliberately interleave observation angles between incidence groups.
                    for rows in plane["co_solved_samples"].values():
                        rows.data[:, 1] = np.where(np.arange(len(rows)) % 3, 15., -40.)
                if disk_shape == "extension":
                    # A missing numeric value preserves row.get defaults by forcing the
                    # ordinary dictionary codec. Other extension data must survive untouched.
                    plane["samples"] = list(plane["samples"])
                    plane["samples"][0].pop("theta_inc_deg")
                    plane["samples"][0]["external"] = {"source": "audit"}
                plane["_recovery_row_counts"] = dict(samples=len(plane["samples"]),
                    **{k: len(v) for k, v in plane["co_solved_samples"].items()})
                dataset.store.save(frequency, plane)
            current = dataset.result()
            measurements = {}
            with measure_loads(measurements):
                histories = finished(current)
                tab.canvas.draw()
            cases[disk_shape + "_record"] = dict(values=capture_visible_values(),
                state=dict(status=tab.lbl_status.text(), history=histories),
                presentation=measurements, expected_compact=disk_shape != "extension")
        # Actual publication and re-open. Guard against an old view holding the successful
        # run folder live, or precomputed columns bypassing the exporter's source verification.
        lifecycle = RecoveryRun.create(root / "lifecycle", dict(geometry_snapshot=snapshot,
            geometry_units="meters", frequencies_ghz=requested[:3], elevations_deg=angles.tolist()),
            {}, "double", False)
        for frequency in requested[:3]:
            lifecycle.save(frequency, synthetic_plane(frequency))
        solved = lifecycle.result()
        ref = weakref.ref(solved["samples"].reader)
        tab.chk_export_after_solve.setChecked(False)
        tab._on_solver_finished(solved, "")
        assert lifecycle.directory.is_dir()
        tab.edit_output.setText(str(root / "after_edit.grim"))
        record = lifecycle.store._path(requested[1])
        original_record = record.read_bytes()
        record.write_bytes(original_record + b"changed after successful display")
        rejected = []
        with (patch.object(solver.QMessageBox, "critical", side_effect=lambda *v: rejected.append(str(v[-1]))),
              patch.object(solver.QMessageBox, "information", return_value=None)):
            tab._export_last_result()
        assert rejected and not (root / "after_edit.grim").exists()
        record.write_bytes(original_record)
        tab.edit_output.setText(str(root / "actual.grim"))
        dialog_errors = []
        with (patch.object(solver.QMessageBox, "critical", side_effect=lambda *v: dialog_errors.append(str(v[-1]))),
              patch.object(solver.QMessageBox, "information", return_value=None)):
            tab._export_last_result()
        repaired_in_place = not dialog_errors
        if dialog_errors:
            # The baseline reader can retain a failed switch's stale frequency key.
            # Record this outcome and open a fresh verified result to finish lifecycle checks.
            assert "NoneType" in dialog_errors[0], dialog_errors
            solved = lifecycle.result()
            ref = weakref.ref(solved["samples"].reader)
            tab._on_solver_finished(solved, "")
            with (patch.object(solver.QMessageBox, "critical", side_effect=AssertionError),
                  patch.object(solver.QMessageBox, "information", return_value=None)):
                tab._export_last_result()
        assert lifecycle.directory.is_dir() and (root / "actual.grim").is_file()
        state = {}
        with np.load(root / "actual.grim", allow_pickle=False) as archive:
            for key in archive.files:
                v = archive[key]
                if v.dtype.kind in "bcfiu":
                    state[key] = [str(v.dtype), list(v.shape), hashlib.sha256(v.tobytes()).hexdigest()]
        assert "frequencies" in state and any(k.startswith("rcs_") for k in state)
        # Stale records must not be overwritten even when verified display values still exist.
        before = (root / "actual.grim").read_bytes()
        tab._last_result_stale = True
        warnings = []
        with patch.object(solver.QMessageBox, "warning", side_effect=lambda *v: warnings.append(str(v[-1]))):
            tab._export_last_result()
        assert len(warnings) == 1 and "geometry changed" in warnings[0].lower()
        assert (root / "actual.grim").read_bytes() == before
        del solved
        finished(dict(samples=[], metadata={}))
        gc.collect()
        assert ref() is None and not lifecycle.directory.exists()
        cases["retry_after_disk_repair"] = dict(repaired_without_reopen=repaired_in_place,
                                                  errors=dialog_errors)
        cases["real_export_release"] = dict(numeric_members=state, released=True, stale_warning=warnings,
                                            post_display_corruption_prevented_export=True)
tab.close()
report = dict(source=checkout.name, case=args.case, host=platform.platform(), numpy=np.__version__,
              python=sys.version.split()[0], pyside6=PySide6.__version__,
              fixture="synthetic fields through RecoveryRun.save/result and offscreen SolverTab",
              display_limit_bytes=getattr(result_table, "_DISPLAY_COLUMN_LIMIT_BYTES", None), results=cases)
args.output.write_text(json.dumps(report, indent=2) + "\n")
print(args.output, {k: v["presentation"] for k, v in cases.items() if "presentation" in v}, flush=True)
