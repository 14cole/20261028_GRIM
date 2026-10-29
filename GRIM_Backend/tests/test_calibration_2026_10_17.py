"""Calibration-workflow numerical audit regressions (2026-10-17).

Synthetic measurement chains with known truth are passed through GRIM's
Range Cal (complex substitution). The exact reference is an independently
coded PEC-sphere Mie series (exp(+j*omega*t), h_n^(2) outgoing waves,
phase referenced to the sphere center), so these tests do not depend on any
GRIM or GHOST reference-theory implementation.
"""

from __future__ import annotations

import json
import unittest
import warnings

import numpy as np
from scipy.special import spherical_jn, spherical_yn

from GRIM_Backend.datasets.constants import C0
from GRIM_Backend.datasets.grid import RcsGrid


_UNITS = {
    "azimuth": "deg",
    "elevation": "deg",
    "frequency": "GHz",
    "rcs_log_unit": "dBsm",
    "rcs_linear_quantity": "sigma_3d",
}


def _mie_pec_backscatter(radius_m: float, frequency_hz: np.ndarray) -> np.ndarray:
    """Complex PEC-sphere backscatter amplitude A with |A|**2 = sigma (m^2).

    exp(+j*omega*t); phase referenced to the sphere center. With the
    monostatic exp(-j*2*k*R) law the specular point (nearer by the radius)
    makes the phase advance as +2*k*a at large k*a.
    """

    out = np.empty(np.size(frequency_hz), dtype=np.complex128)
    for index, frequency in enumerate(np.atleast_1d(frequency_hz)):
        k = 2.0 * np.pi * float(frequency) / C0
        x = k * radius_m
        n = np.arange(1, int(x + 4.05 * x ** (1.0 / 3.0) + 12) + 1)
        jn = spherical_jn(n, x)
        jnp = spherical_jn(n, x, derivative=True)
        h2 = jn - 1j * spherical_yn(n, x)
        h2p = jnp - 1j * spherical_yn(n, x, derivative=True)
        a_n = -(jn + x * jnp) / (h2 + x * h2p)
        b_n = -jn / h2
        series = np.sum((-1.0) ** n * (2 * n + 1) * (a_n - b_n))
        out[index] = 1j * (2.0 * np.pi / k) / (2.0 * np.sqrt(np.pi)) * series
    return out


def _grid(values, azimuths, frequencies_ghz, polarizations, *, extra=None, units=None):
    return RcsGrid(
        np.asarray(azimuths, dtype=float),
        [0.0],
        np.asarray(frequencies_ghz, dtype=float),
        list(polarizations),
        rcs=np.asarray(values, dtype=np.complex128),
        units=dict(units or _UNITS),
        extra=dict(extra or {}),
    )


class _Chain:
    """Truth, system response, background, and a farther calibration sphere."""

    def __init__(self, polarizations=("VV", "HH")):
        self.pols = list(polarizations)
        self.f_ghz = np.linspace(8.0, 12.0, 81)
        f_hz = self.f_ghz * 1.0e9
        k = 2.0 * np.pi * f_hz / C0
        self.az = np.linspace(-4.0, 4.0, 9)
        count = len(self.pols)
        truth = np.zeros((len(self.az), 1, len(f_hz), count), dtype=np.complex128)
        look = np.stack(
            [np.cos(np.deg2rad(self.az)), np.sin(np.deg2rad(self.az))], axis=-1
        )
        for x, y, amplitude in ((0.3, 0.0, 0.5 + 0.2j), (-0.2, 0.1, 0.3 - 0.4j)):
            phase = np.exp(2j * k[None, :] * (look @ np.array([x, y]))[:, None])
            for pol in range(count):
                truth[:, 0, :, pol] += amplitude * (1.0 - 0.3 * pol) * phase
        self.truth = truth
        delays = 3.1e-9 + 0.1e-9 * np.arange(count)
        gains = 1.0e-3 * (1.0 + 0.25 * np.arange(count))
        self.system = (
            gains[None, :]
            * (1.0 + 0.2 * np.sin(2.0 * np.pi * f_hz / 1.3e9))[:, None]
            * np.exp(-2j * np.pi * f_hz[:, None] * delays[None, :])
        )
        self.offset_m = 0.4
        self.sphere = _mie_pec_backscatter(0.1524, f_hz)
        self.offset_phase = np.exp(-2j * k * self.offset_m)
        rng = np.random.default_rng(20261017)
        self.background_dut = 0.05 * (
            rng.normal(size=truth.shape) + 1j * rng.normal(size=truth.shape)
        )
        self.background_cal = 0.05 * (
            rng.normal(size=(1, 1, len(f_hz), count))
            + 1j * rng.normal(size=(1, 1, len(f_hz), count))
        )

    def exact_values(self, cross_pol_zero=()):
        values = np.repeat(self.sphere[:, None], len(self.pols), axis=1)
        for pol in cross_pol_zero:
            values[:, self.pols.index(pol)] = 0.0
        return values[None, None]

    def exact(self, **kwargs):
        return _grid(self.exact_values(), [0.0], self.f_ghz, self.pols, **kwargs)

    def measured_cal(self, exact_values=None, leakage=None, **kwargs):
        exact_values = self.exact_values() if exact_values is None else exact_values
        scattered = exact_values[0, 0].copy()
        if leakage is not None:
            scattered = scattered + leakage
        values = scattered * self.offset_phase[:, None] * self.system
        return _grid(values[None, None], [0.0], self.f_ghz, self.pols, **kwargs)

    def dut(self, **kwargs):
        return _grid(
            self.truth * self.system[None, None], self.az, self.f_ghz, self.pols, **kwargs
        )


class IndependentSphereReferenceTest(unittest.TestCase):
    def test_mie_reference_limits_and_center_phase_convention(self) -> None:
        radius = 0.1
        # Rayleigh: sigma = 9*pi*a^2*(ka)^4 for ka << 1.
        f_low = 5.0e6
        ka = 2.0 * np.pi * f_low / C0 * radius
        sigma = abs(_mie_pec_backscatter(radius, f_low)[0]) ** 2
        self.assertAlmostEqual(sigma / (9.0 * np.pi * radius**2 * ka**4), 1.0, places=4)
        # Optical: sigma -> pi*a^2 and phase advances by +2*k*a (center reference).
        f_high = np.linspace(30.0e9, 31.0e9, 41)
        amplitude = _mie_pec_backscatter(radius, f_high)
        np.testing.assert_allclose(
            np.abs(amplitude) ** 2, np.pi * radius**2, rtol=1.0e-2
        )
        slope = np.polyfit(
            2.0 * np.pi * f_high / C0, np.unwrap(np.angle(amplitude)), 1
        )[0]
        self.assertAlmostEqual(slope, 2.0 * radius, places=3)


class RangeCalChainTest(unittest.TestCase):
    def test_recovers_truth_through_system_offset_and_background(self) -> None:
        chain = _Chain()
        dut_raw = _grid(
            chain.truth * chain.system[None, None]
            + chain.background_dut * chain.system[None, None],
            chain.az, chain.f_ghz, chain.pols,
        )
        dut_background = _grid(
            chain.background_dut * chain.system[None, None],
            chain.az, chain.f_ghz, chain.pols,
        )
        cal_raw = chain.measured_cal(
            leakage=chain.background_cal[0, 0] / chain.offset_phase[:, None]
        )
        cal_background = _grid(
            chain.background_cal * chain.system[None, None],
            [0.0], chain.f_ghz, chain.pols,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            dut = dut_raw.coherent_subtract(dut_background)
            cal = cal_raw.coherent_subtract(cal_background)
        # Reference channels deliberately in a different order/case.
        cal_reordered = _grid(
            cal.rcs[..., ::-1], [0.0], chain.f_ghz, [p.lower() for p in chain.pols[::-1]]
        )
        result = dut.range_calibrate(
            cal_reordered,
            chain.exact(),
            chain.offset_m,
            allow_singleton_angular_broadcast=True,
            maximum_correction_gain_db=None,
        )
        scale = np.max(np.abs(chain.truth))
        np.testing.assert_allclose(result.rcs, chain.truth, rtol=0.0, atol=1.0e-12 * scale)
        np.testing.assert_allclose(
            result.rcs_power, np.abs(chain.truth) ** 2, rtol=1.0e-10
        )
        # The offset sign matters: the opposite sign is grossly wrong.
        wrong = dut.range_calibrate(
            cal_reordered, chain.exact(), -chain.offset_m,
            allow_singleton_angular_broadcast=True, maximum_correction_gain_db=None,
        )
        self.assertGreater(np.max(np.abs(wrong.rcs - chain.truth)), 0.5 * scale)

    def test_frequency_units_are_honored(self) -> None:
        chain = _Chain()
        for unit, factor in (("Hz", 1.0e9), ("MHz", 1.0e3)):
            units = {**_UNITS, "frequency": unit}
            freqs = chain.f_ghz * factor
            dut = _grid(chain.dut().rcs, chain.az, freqs, chain.pols, units=units)
            cal = _grid(chain.measured_cal().rcs, [0.0], freqs, chain.pols, units=units)
            exact = _grid(chain.exact().rcs, [0.0], freqs, chain.pols, units=units)
            result = dut.range_calibrate(
                cal, exact, chain.offset_m,
                allow_singleton_angular_broadcast=True, maximum_correction_gain_db=None,
            )
            np.testing.assert_allclose(result.rcs, chain.truth, atol=1.0e-12)

    def test_zero_exact_cross_pol_is_masked_not_fabricated_as_null(self) -> None:
        # Sphere exact HV = 0, measured HV = polarization leakage. The old
        # behaviour returned HV = 0+0j (-inf dBsm) at every bin while the true
        # DUT cross-pol reached about -15 dBsm.
        chain = _Chain(("VV", "HH", "HV"))
        exact_values = chain.exact_values(cross_pol_zero=("HV",))
        leakage = np.zeros((len(chain.f_ghz), 3), dtype=np.complex128)
        leakage[:, 2] = 0.01 * chain.sphere
        measured = chain.measured_cal(exact_values=exact_values, leakage=leakage)
        exact = _grid(exact_values, [0.0], chain.f_ghz, chain.pols)
        result = chain.dut().range_calibrate(
            measured, exact, chain.offset_m,
            allow_singleton_angular_broadcast=True, maximum_correction_gain_db=None,
        )
        self.assertTrue(np.all(np.isnan(result.rcs[..., 2])))
        np.testing.assert_allclose(result.rcs[..., :2], chain.truth[..., :2], atol=1.0e-12)
        record = json.loads(result.extra["range_calibration_json"])
        self.assertEqual(record["correction_gain_db"]["zero_factor_count"], len(chain.f_ghz))
        self.assertEqual(
            record["correction_gain_db"]["masked_output_bin_count"],
            len(chain.az) * len(chain.f_ghz),
        )
        self.assertEqual(record["zero_exact_reference_policy"], "masked")

    def test_magnitude_only_inputs_are_refused(self) -> None:
        chain = _Chain()
        power = np.abs(chain.dut().rcs) ** 2
        power[0, 0, 0, 0] = 0.0  # a known zero must not leak through as output
        dut_power = RcsGrid(
            chain.az, [0.0], chain.f_ghz, chain.pols, rcs_power=power, units=dict(_UNITS)
        )
        with self.assertRaisesRegex(ValueError, "DUT has no finite nonzero complex"):
            dut_power.range_calibrate(
                chain.measured_cal(), chain.exact(), chain.offset_m,
                allow_singleton_angular_broadcast=True,
            )
        exact_power = RcsGrid(
            [0.0], [0.0], chain.f_ghz, chain.pols,
            rcs_power=np.abs(chain.exact().rcs) ** 2, units=dict(_UNITS),
        )
        with self.assertRaisesRegex(ValueError, "exact reference has no finite nonzero"):
            chain.dut().range_calibrate(
                chain.measured_cal(), exact_power, chain.offset_m,
                allow_singleton_angular_broadcast=True, maximum_correction_gain_db=None,
            )
        measured_power = RcsGrid(
            [0.0], [0.0], chain.f_ghz, chain.pols,
            rcs_power=np.abs(chain.measured_cal().rcs) ** 2, units=dict(_UNITS),
        )
        with self.assertRaisesRegex(ValueError, "measured calibration has no finite"):
            chain.dut().range_calibrate(
                measured_power, chain.exact(), chain.offset_m,
                allow_singleton_angular_broadcast=True, maximum_correction_gain_db=None,
            )

    def test_declared_positive_two_way_range_phase_is_refused(self) -> None:
        chain = _Chain()
        for role in ("dut", "measured", "exact"):
            for key, value in (
                ("range_phase_convention", "exp(+j2kR)"),
                ("phase_law", "S ~ exp(+j*2*k*R)"),
            ):
                with self.subTest(role=role, key=key):
                    extras = {"dut": {}, "measured": {}, "exact": {}}
                    extras[role] = {key: value}
                    with self.assertRaisesRegex(ValueError, "two-way range phase"):
                        chain.dut(extra=extras["dut"]).range_calibrate(
                            chain.measured_cal(extra=extras["measured"]),
                            chain.exact(extra=extras["exact"]),
                            chain.offset_m,
                            allow_singleton_angular_broadcast=True,
                        )
        declared = {"range_phase_convention": "exp(-j2kR)"}
        result = chain.dut(extra=declared).range_calibrate(
            chain.measured_cal(extra=declared), chain.exact(), chain.offset_m,
            allow_singleton_angular_broadcast=True, maximum_correction_gain_db=None,
        )
        np.testing.assert_allclose(result.rcs, chain.truth, atol=1.0e-12)
        record = json.loads(result.extra["range_calibration_json"])
        self.assertEqual(
            record["declared_two_way_range_phase"],
            {"DUT": "negative", "measured calibration": "negative"},
        )

    def test_reference_grid_mismatch_is_refused_not_interpolated(self) -> None:
        chain = _Chain()
        coarse = chain.f_ghz[::2]
        cal = _grid(chain.measured_cal().rcs[:, :, ::2], [0.0], coarse, chain.pols)
        exact = _grid(chain.exact().rcs[:, :, ::2], [0.0], coarse, chain.pols)
        with self.assertRaisesRegex(ValueError, "frequency axes differ"):
            chain.dut().range_calibrate(
                cal, exact, chain.offset_m, allow_singleton_angular_broadcast=True
            )


if __name__ == "__main__":
    unittest.main()
