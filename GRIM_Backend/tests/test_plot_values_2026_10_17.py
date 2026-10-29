"""Plotted values, readouts and report values against independent formulas.

Each test synthesizes an RcsGrid with known samples, renders it through the
same mode entry points the Plotting GUI uses (or the PPT report builders),
extracts the drawn artist data, and compares it with values computed here
directly from the stored samples.
"""
from __future__ import annotations

from types import SimpleNamespace
import unittest
import warnings

import numpy as np

from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.plotting.modes import (
    azimuth_polar_mode,
    azimuth_rect_mode,
    cdf_mode,
    common,
    elevation_sweep_mode,
    frequency_mode,
    sector_stats_mode,
    waterfall_mode,
)
from GRIM_Backend.reports.plot_data import build_azimuth_specs, build_frequency_spec
from GRIM_Backend.scripting.plotting import plot_datasets
from test_plot_renderer_correctness import _RendererHarness

C0 = 299_792_458.0
FREQUENCY_SCALE = {"GHz": 1.0e9, "MHz": 1.0e6, "Hz": 1.0}


def _dataset(kind, *, unit="GHz", wrap=None):
    """Six azimuths, two elevations, two frequencies, one polarization.

    Sample [2, 0, 0] has zero power and [3, 0, 0] is missing. For the
    partial-phase case [4, 0, 0] has known power and unknown phase.
    """
    azimuths = np.array([-20.0, -10.0, 0.0, 10.0, 20.0, 30.0])
    frequencies = {"GHz": [9.0, 10.0], "MHz": [9000.0, 10000.0], "Hz": [9.0e9, 1.0e10]}[unit]
    shape = (6, 2, 2, 1)
    rng = np.random.default_rng(17)
    magnitude = rng.uniform(0.1, 3.0, shape)
    phase = rng.uniform(-np.pi, np.pi, shape)
    magnitude[2, 0, 0, 0] = 0.0
    sigma_2d = kind == "raw_2d"
    units = {
        "frequency": unit,
        "rcs_linear_quantity": "sigma_2d" if sigma_2d else "sigma_3d",
        "rcs_log_unit": "dBke" if sigma_2d else "dBsm",
    }
    if wrap:
        units["phase_wrap"] = wrap
    field = magnitude * np.exp(1j * phase)
    field[3, 0, 0, 0] = np.nan
    if kind == "complex":
        return RcsGrid(azimuths, [0.0, 5.0], frequencies, ["HH"], rcs=field, units=units)
    if kind in {"raw_2d", "raw_3d"}:
        return RcsGrid(azimuths, [0.0, 5.0], frequencies, ["HH"], rcs=field,
                       rcs_storage_domain="raw_field", units=units)
    power = magnitude ** 2
    power[3, 0, 0, 0] = np.nan
    if kind == "power":
        return RcsGrid(azimuths, [0.0, 5.0], frequencies, ["HH"], rcs_power=power, units=units)
    phase[4, 0, 0, 0] = np.nan
    return RcsGrid(azimuths, [0.0, 5.0], frequencies, ["HH"],
                   rcs_power=power, rcs_phase=phase, units=units)


def _physical_power(dataset, raw_field):
    """Independent raw-field normalization from docs/complex_storage.md."""
    if dataset.linear_quantity() == "sigma_2d":
        k = 2.0 * np.pi * np.asarray(dataset.frequencies, float) * FREQUENCY_SCALE[dataset.units["frequency"]] / C0
        return np.abs(raw_field) ** 2 / (4.0 * k[None, None, :, None])
    return 4.0 * np.pi * np.abs(raw_field) ** 2


def _expected(dataset, azimuth, elevation, frequency, display):
    power = np.asarray(dataset.power[azimuth, elevation, frequency, 0], dtype=float)
    if display == "linear":
        return power
    if display == "phase":
        field = dataset.rcs_slice((azimuth, elevation, frequency, 0))
        valid = np.isfinite(field) & (np.abs(field) > 0)
        degrees = np.where(valid, np.degrees(np.angle(field)), np.nan)
        if dataset.units.get("phase_wrap") == "0_360":
            return np.mod(degrees, 360.0)
        return np.mod(degrees + 180.0, 360.0) - 180.0
    frequency_hz = np.asarray(dataset.frequencies)[frequency] * FREQUENCY_SCALE[dataset.units["frequency"]]
    positive = np.where(power > 0, power, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        if dataset.default_log_unit() == "dBke":
            return 10.0 * np.log10(2.0 * np.pi * frequency_hz / C0 * positive)
        return 10.0 * np.log10(positive)


def _owner(test, named, selections, *, display="db", polar=False):
    owner = _RendererHarness(named, selections=selections, phase=display == "phase")
    if display == "linear":
        owner.combo_plot_scale.data = "linear"
    if polar:
        owner.plot_ax.remove()
        owner.plot_ax = owner.plot_figure.add_subplot(111, projection="polar")
    test.addCleanup(owner.plot_figure.clear)
    test.addCleanup(owner._release_native_plot_samples)
    return owner


def _curves(axes):
    return [line for line in axes.lines if not str(line.get_label()).startswith("_")]


def _assert_same(test, actual, expected):
    actual, expected = np.asarray(actual, float), np.asarray(expected, float)
    test.assertEqual(actual.shape, expected.shape)
    np.testing.assert_array_equal(np.isnan(actual), np.isnan(expected))
    np.testing.assert_allclose(actual[~np.isnan(actual)], expected[~np.isnan(expected)],
                               rtol=0.0, atol=1.0e-9)


class StoredSampleTests(unittest.TestCase):
    def test_raw_field_power_uses_documented_normalization(self):
        for kind in ("raw_2d", "raw_3d"):
            with self.subTest(kind=kind):
                dataset = _dataset(kind, unit="MHz")
                field = dataset._complex  # the stored raw solver field
                np.testing.assert_allclose(np.asarray(dataset.power), _physical_power(dataset, field),
                                           rtol=1.0e-12, equal_nan=True)


class LineModeValueTests(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter("ignore", RuntimeWarning)

    def test_azimuth_rect_and_polar_values_units_and_gaps(self):
        for kind in ("complex", "power", "partial", "raw_2d", "raw_3d"):
            for unit in ("GHz", "MHz", "Hz"):
                for wrap in (None, "0_360", "-180_180"):
                    for display in ("db", "linear", "phase"):
                        if display == "phase" and kind == "power":
                            continue
                        dataset = _dataset(kind, unit=unit, wrap=wrap)
                        for mode, polar in ((azimuth_rect_mode, False), (azimuth_polar_mode, True)):
                            with self.subTest(kind=kind, unit=unit, wrap=wrap, display=display, polar=polar):
                                owner = _owner(self, [("A", dataset)], dict(
                                    azimuth=dataset.azimuths, elevation=[0.0],
                                    frequency=[dataset.frequencies[0]]), display=display, polar=polar)
                                mode.render(owner)
                                line, = _curves(owner.plot_ax)
                                expected_x = np.deg2rad(dataset.azimuths) if polar else dataset.azimuths
                                _assert_same(self, line.get_xdata(), expected_x)
                                expected = _expected(dataset, slice(None), 0, 0, display)
                                _assert_same(self, line.get_ydata(), expected)
                                # Zero power and missing samples are gaps, never floored.
                                self.assertTrue(np.isnan(line.get_ydata()[3]))
                                if display != "linear":
                                    self.assertTrue(np.isnan(line.get_ydata()[2]))
                                else:
                                    self.assertEqual(line.get_ydata()[2], 0.0)
                                if display == "phase" and kind == "partial":
                                    self.assertTrue(np.isnan(line.get_ydata()[4]))
                                if polar:
                                    self.assertEqual(owner.plot_ax.get_theta_direction(), -1)
                                    self.assertAlmostEqual(owner.plot_ax.get_theta_offset(), np.pi / 2)
                                else:
                                    quantity = "Scattering Width" if kind == "raw_2d" else "RCS"
                                    unit_label = {"db": dataset.default_log_unit(), "phase": "deg",
                                                  "linear": "m" if kind == "raw_2d" else "m²"}[display]
                                    if display == "phase":
                                        self.assertEqual(owner.plot_ax.get_ylabel(), "Phase (deg)")
                                    else:
                                        self.assertEqual(owner.plot_ax.get_ylabel(), f"{quantity} ({unit_label})")
                                    self.assertIn(f"Freq {dataset.frequencies[0]:.12g} {unit}", line.get_label())

    def test_frequency_and_elevation_sweeps_index_the_selected_cut(self):
        for kind in ("complex", "power", "partial", "raw_2d"):
            for display in ("db", "linear", "phase"):
                if display == "phase" and kind == "power":
                    continue
                dataset = _dataset(kind, unit="MHz")
                cases = (
                    (frequency_mode, dict(azimuth=[dataset.azimuths[2]], elevation=[0.0],
                                          frequency=dataset.frequencies), (2, 0, slice(None)), dataset.frequencies),
                    (frequency_mode, dict(azimuth=[dataset.azimuths[1]], elevation=[5.0],
                                          frequency=dataset.frequencies), (1, 1, slice(None)), dataset.frequencies),
                    (elevation_sweep_mode, dict(azimuth=[dataset.azimuths[2]], elevation=dataset.elevations,
                                                frequency=[dataset.frequencies[0]]), (2, slice(None), 0), dataset.elevations),
                    (elevation_sweep_mode, dict(azimuth=[dataset.azimuths[4]], elevation=dataset.elevations,
                                                frequency=[dataset.frequencies[1]]), (4, slice(None), 1), dataset.elevations),
                )
                for mode, selections, index, x in cases:
                    with self.subTest(kind=kind, display=display, mode=mode.__name__, index=index):
                        owner = _owner(self, [("A", dataset)], selections, display=display)
                        mode.render(owner)
                        line, = _curves(owner.plot_ax)
                        _assert_same(self, line.get_xdata(), x)
                        _assert_same(self, line.get_ydata(), _expected(dataset, *index, display))

    def test_overlay_legend_identifies_each_dataset_and_native_unit(self):
        azimuths = np.array([0.0, 10.0, 20.0])
        low = RcsGrid(azimuths, [0.0], [9.0], ["HH"], rcs_power=np.full((3, 1, 1, 1), 1.0))
        high = RcsGrid(azimuths, [0.0], [9.0], ["HH"], rcs_power=np.full((3, 1, 1, 1), 100.0))
        width = RcsGrid(azimuths, [0.0], [9.0], ["HH"], rcs_power=np.full((3, 1, 1, 1), 10.0),
                        units={"rcs_linear_quantity": "sigma_2d", "rcs_log_unit": "dBke"})
        owner = _owner(self, [("low", low), ("high", high), ("width", width)],
                       dict(azimuth=azimuths, elevation=[0.0], frequency=[9.0]))
        azimuth_rect_mode.render(owner)
        expected = {
            "low [dBsm]": 0.0,
            "high [dBsm]": 20.0,
            "width [dBke]": 10.0 * np.log10(2.0 * np.pi * 9.0e9 / C0 * 10.0),
        }
        lines = _curves(owner.plot_ax)
        self.assertEqual(len(lines), 3)
        for line in lines:
            head = line.get_label().split(" | ")[0]
            np.testing.assert_allclose(line.get_ydata(), expected[head])
        legend = owner.plot_ax.get_legend()
        for text, handle, line in zip(legend.get_texts(), legend.legend_handles, lines):
            self.assertEqual(text.get_text(), line.get_label())
            self.assertEqual(handle.get_color(), line.get_color())
        self.assertEqual(owner.plot_ax.get_ylabel(), "Mixed dB")

    def test_gui_and_python_replay_draw_identical_values(self):
        for kind in ("complex", "partial", "raw_2d"):
            for display in ("db", "linear", "phase"):
                dataset = _dataset(kind, unit="MHz", wrap="0_360")
                for mode_name, mode, selections in (
                    ("azimuth_rect", azimuth_rect_mode, dict(azimuth=dataset.azimuths, elevation=[0.0], frequency=[9000.0])),
                    ("frequency", frequency_mode, dict(azimuth=dataset.azimuths[:3], elevation=[0.0], frequency=dataset.frequencies)),
                    ("elevation_sweep", elevation_sweep_mode, dict(azimuth=[0.0], elevation=dataset.elevations, frequency=[9000.0])),
                ):
                    with self.subTest(kind=kind, display=display, mode=mode_name):
                        owner = _owner(self, [("A", dataset)], selections, display=display)
                        mode.render(owner)
                        figure = plot_datasets(
                            [("A", dataset)], mode=mode_name, azimuths=selections["azimuth"],
                            elevations=selections["elevation"], frequencies=selections["frequency"],
                            polarization="HH", phase=display == "phase",
                            scale="linear" if display == "linear" else "dbsm")
                        self.addCleanup(figure.clear)
                        for gui, replay in zip(_curves(owner.plot_ax), _curves(figure.axes[0]), strict=True):
                            _assert_same(self, gui.get_xdata(), replay.get_xdata())
                            _assert_same(self, gui.get_ydata(), replay.get_ydata())


class ImageAndStatisticTests(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter("ignore", RuntimeWarning)

    def test_waterfall_cells_edges_and_shared_colorbar(self):
        for kind in ("complex", "power", "partial", "raw_2d"):
            for display in ("db", "linear", "phase"):
                if display == "phase" and kind == "power":
                    continue
                dataset = _dataset(kind, unit="MHz", wrap="0_360" if kind == "complex" else None)
                with self.subTest(kind=kind, display=display):
                    owner = _owner(self, [("A", dataset)], dict(
                        azimuth=dataset.azimuths, elevation=dataset.elevations,
                        frequency=dataset.frequencies), display=display)
                    owner.chk_colorbar.checked = True
                    waterfall_mode.render(owner)
                    self.assertEqual(len(owner.plot_axes), 2)
                    every = []
                    for elevation, axes in enumerate(owner.plot_axes):
                        mesh = axes.collections[0]
                        values = np.ma.filled(mesh.get_array(), np.nan).reshape(2, 6)
                        expected = np.stack([_expected(dataset, slice(None), elevation, f, display)
                                             for f in range(2)])
                        _assert_same(self, values, expected)
                        every.append(expected[np.isfinite(expected)])
                        coordinates = mesh.get_coordinates()
                        np.testing.assert_allclose(coordinates[0, :, 0], np.r_[dataset.azimuths - 5.0, 35.0])
                        np.testing.assert_allclose(coordinates[:, 0, 1], [8500.0, 9500.0, 10500.0])
                    every = np.concatenate(every)
                    np.testing.assert_allclose(owner.plot_colorbars[0].mappable.get_clim(),
                                               (every.min(), every.max()))

    def test_cdf_matches_empirical_distribution_with_zero_mass(self):
        for kind in ("complex", "power", "raw_2d"):
            for display in ("db", "linear"):
                dataset = _dataset(kind, unit="MHz")
                with self.subTest(kind=kind, display=display):
                    owner = _owner(self, [("A", dataset)], dict(
                        azimuth=dataset.azimuths, elevation=dataset.elevations,
                        frequency=dataset.frequencies), display=display)
                    cdf_mode.render(owner)
                    line, = _curves(owner.plot_ax)
                    power = np.asarray(dataset.power, float)[..., 0]
                    levels = np.stack([[ _expected(dataset, slice(None), e, f, display)
                                         for f in range(2)] for e in range(2)])
                    levels = np.moveaxis(levels, -1, 0)
                    valid = np.isfinite(power)
                    population = np.sort(np.where(power == 0, -np.inf, levels)[valid]
                                         if display == "db" else levels[valid])
                    distinct = np.unique(population[np.isfinite(population)])
                    _assert_same(self, line.get_xdata()[1:-1], distinct)
                    _assert_same(self, line.get_ydata()[1:-1],
                                 [100.0 * np.mean(population <= q) for q in distinct])
                    zero_fraction = 100.0 * np.mean(population == -np.inf) if display == "db" else 0.0
                    self.assertAlmostEqual(line.get_ydata()[0], zero_fraction)
                    self.assertIn(f"median {np.median(population):.4g}", line.get_label())

    def test_sector_statistics_match_numpy_in_linear_power(self):
        dataset = _dataset("raw_2d")

        class Controls:
            statistic = "mean"

            def sector_statistic(self):
                return self.statistic

            def sector_percentile(self):
                return 75.0

            def sector_text(self, unit=None):
                return "20"

        power = np.asarray(dataset.power[:, 0, 0, 0], float)
        azimuths = dataset.azimuths
        members = [(azimuths >= -20) & (azimuths < 0), (azimuths >= 0) & (azimuths < 20),
                   (azimuths >= 20) & (azimuths <= 30)]
        reducers = {"mean": np.mean, "median": np.median, "min": np.min, "max": np.max,
                    "percentile": lambda values: np.percentile(values, 75.0)}
        column = {"mean": 6, "median": 7, "min": 8, "max": 9, "percentile": 10}
        k = 2.0 * np.pi * 9.0e9 / C0
        for display in ("db", "linear"):
            for statistic, reducer in reducers.items():
                with self.subTest(display=display, statistic=statistic):
                    owner = _owner(self, [("A", dataset)], dict(
                        azimuth=azimuths, elevation=[0.0], frequency=[9.0]), display=display)
                    owner.analysis_controls = Controls()
                    owner.analysis_controls.statistic = statistic
                    sector_stats_mode.render(owner)
                    rows = owner.plot_figure._grim_sector_table["rows"]
                    expected = []
                    for member in members:
                        values = power[member]
                        value = reducer(values[np.isfinite(values)])
                        if display == "db":
                            with np.errstate(divide="ignore"):
                                value = 10.0 * np.log10(k * value)
                        expected.append(value)
                    np.testing.assert_allclose([row[column[statistic]] for row in rows], expected)
                    self.assertEqual([row[5] for row in rows], [2, 1, 2])


class DisplayDecimationTests(unittest.TestCase):
    def _fragmented(self, count, spike, null, rng, missing_fraction):
        y = np.sin(np.arange(count) / 500.0)
        missing = rng.integers(0, count, size=int(count * missing_fraction))
        y[missing[(missing != spike) & (missing != null)]] = np.nan
        y[spike], y[null] = 100.0, -100.0
        return np.arange(count, dtype=float), y

    def _assert_never_bridges_missing(self, x, y, shown_x, shown_y):
        positions = np.searchsorted(x, shown_x)
        for left in range(len(positions) - 1):
            if np.isfinite(shown_y[left:left + 2]).all():
                self.assertTrue(np.isfinite(y[positions[left]:positions[left + 1] + 1]).all())

    def test_fragmented_line_keeps_narrow_spike_and_null(self):
        rng = np.random.default_rng(3)
        for count, budget, fraction in ((50_000, 20_000, 0.02), (50_000, 2_000, 0.02),
                                        (123_457, 2_000, 0.3), (20_001, 37, 0.01)):
            with self.subTest(count=count, budget=budget, fraction=fraction):
                spike, null = (int(value) for value in rng.integers(1, count - 1, size=2))
                x, y = self._fragmented(count, spike, null, rng, fraction)
                shown_x, shown_y, reduced = common.decimate_line(x, y, max_points=budget)
                self.assertTrue(reduced)
                self.assertLessEqual(len(shown_x), budget)
                self.assertEqual(np.nanmax(shown_y), 100.0)
                self.assertEqual(np.nanmin(shown_y), -100.0)
                self._assert_never_bridges_missing(x, y, shown_x, shown_y)

    def test_fragmented_envelope_keeps_both_edge_extrema(self):
        rng = np.random.default_rng(4)
        for budget in (2_000, 20_000):
            with self.subTest(budget=budget):
                x, y = self._fragmented(60_000, 123, 45_678, rng, 0.05)
                shown_x, lower, upper, _count, reduced = common.decimate_envelope(
                    x, y - 1.0, y + 1.0, max_points=budget)
                self.assertTrue(reduced)
                self.assertLessEqual(len(shown_x), budget)
                self.assertEqual(np.nanmax(upper), 101.0)
                self.assertEqual(np.nanmin(lower), -101.0)

    def test_gui_azimuth_curve_with_missing_samples_keeps_peak_and_null(self):
        count = 60_001
        azimuths = np.linspace(-180.0, 180.0, count)
        power = 10.0 ** (np.sin(np.arange(count) / 300.0) / 10.0)
        rng = np.random.default_rng(5)
        power[rng.integers(0, count, size=count // 40)] = np.nan
        power[31_337], power[7_001] = 1.0e6, 1.0e-6
        dataset = RcsGrid(azimuths, [0.0], [9.0], ["HH"], rcs_power=power.reshape(count, 1, 1, 1))
        owner = _owner(self, [("A", dataset)], dict(azimuth=azimuths, elevation=[0.0], frequency=[9.0]))
        azimuth_rect_mode.render(owner)
        line, = _curves(owner.plot_ax)
        self.assertLessEqual(len(line.get_xdata()), common.MAX_LINE_POINTS)
        self.assertEqual(np.nanmax(line.get_ydata()), 60.0)
        self.assertEqual(np.nanmin(line.get_ydata()), -60.0)
        # Markers still read the native samples.
        native_x, native_y = owner._marker_arrays(line)
        self.assertEqual(len(native_x), count)
        self.assertEqual(native_y[31_337], 60.0)


class ReadoutTests(unittest.TestCase):
    def test_polar_hover_reads_plotted_azimuth_unit_not_radians(self):
        azimuths = np.array([0.0, 90.0, 180.0, 270.0])
        dataset = RcsGrid(azimuths, [0.0], [9.0], ["HH"],
                          rcs_power=np.array([1.0, 10.0, 100.0, 1.0e-3]).reshape(4, 1, 1, 1))
        owner = _owner(self, [("A", dataset)], dict(azimuth=azimuths, elevation=[0.0], frequency=[9.0]),
                       polar=True)
        azimuth_polar_mode.render(owner)
        label = SimpleNamespace(text=None)
        label.setText = lambda text: setattr(label, "text", text)
        owner._on_plot_hover(SimpleNamespace(inaxes=owner.plot_ax, xdata=np.deg2rad(270.0), ydata=5.0), label)
        self.assertEqual(label.text, "x: -90.00   y: 5.00")
        owner._on_plot_hover(SimpleNamespace(inaxes=owner.plot_ax, xdata=np.deg2rad(45.0), ydata=-3.0), label)
        self.assertEqual(label.text, "x: 45.00   y: -3.00")

    def test_polar_marker_reads_sample_value_and_tick_convention(self):
        azimuths = np.array([0.0, 90.0, 180.0, 270.0])
        dataset = RcsGrid(azimuths, [0.0], [9.0], ["HH"],
                          rcs_power=np.array([1.0, 10.0, 100.0, 1.0e-3]).reshape(4, 1, 1, 1))
        owner = _owner(self, [("A", dataset)], dict(azimuth=azimuths, elevation=[0.0], frequency=[9.0]),
                       polar=True)
        azimuth_polar_mode.render(owner)
        line, = _curves(owner.plot_ax)
        texts = [owner._marker_text({"line": line, "index": index, "number": 1,
                                     "key": line._grim_dataset_key}, None).splitlines()[1:]
                 for index in range(4)]
        self.assertEqual([text[0] for text in texts],
                         ["x 0 deg", "x 90 deg", "x 180 deg", "x -90 deg"])
        self.assertEqual([text[1] for text in texts],
                         ["y 0 dBsm", "y 10 dBsm", "y 20 dBsm", "y -30 dBsm"])
        tick_labels = [tick.get_text() for tick in owner.plot_ax.get_xticklabels()]
        self.assertIn("180", tick_labels)
        self.assertNotIn("-180", tick_labels)


class ReportValueTests(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter("ignore", RuntimeWarning)

    def _gui_line(self, dataset, display):
        owner = _owner(self, [("A", dataset)], dict(azimuth=dataset.azimuths, elevation=[0.0],
                                                     frequency=[dataset.frequencies[0]]), display=display)
        azimuth_rect_mode.render(owner)
        line, = _curves(owner.plot_ax)
        return line.get_xdata(), line.get_ydata()

    def test_report_azimuth_values_match_plotting_view(self):
        for kind in ("complex", "power", "partial", "raw_2d"):
            for wrap in (None, "0_360"):
                for quantity, display in (("magnitude", "db"), ("phase", "phase")):
                    if quantity == "phase" and kind == "power":
                        continue
                    dataset = _dataset(kind, wrap=wrap)
                    with self.subTest(kind=kind, wrap=wrap, quantity=quantity):
                        spec, = build_azimuth_specs([("A", dataset)], frequencies=[9.0], elevation=0.0,
                                                    polarization="HH", quantity=quantity)
                        series, = spec.series
                        gui_x, gui_y = self._gui_line(dataset, display)
                        _assert_same(self, series.x, gui_x)
                        _assert_same(self, series.y, gui_y)
                        # Zero power has no phase; it is a gap, not 0 deg.
                        self.assertTrue(np.isnan(series.y[2]))

    def test_report_frequency_values_match_plotting_view(self):
        for kind in ("complex", "partial", "raw_2d"):
            for quantity, display in (("magnitude", "db"), ("phase", "phase")):
                dataset = _dataset(kind, unit="MHz", wrap="0_360")
                with self.subTest(kind=kind, quantity=quantity):
                    spec = build_frequency_spec([("A", dataset)], azimuth=0.0, elevation=0.0,
                                                polarization="HH", quantity=quantity,
                                                frequency_display_unit="MHz")
                    series, = spec.series
                    owner = _owner(self, [("A", dataset)], dict(
                        azimuth=[0.0], elevation=[0.0], frequency=dataset.frequencies), display=display)
                    frequency_mode.render(owner)
                    line, = _curves(owner.plot_ax)
                    _assert_same(self, series.x, line.get_xdata())
                    _assert_same(self, series.y, line.get_ydata())


if __name__ == "__main__":
    unittest.main()
