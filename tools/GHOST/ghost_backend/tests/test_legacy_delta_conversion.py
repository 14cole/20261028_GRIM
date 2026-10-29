"""The retired GHOST "delta" concept: decode-time conversion and no gates.

Legacy deltas tagged ``power_domain='delta_amp_sq'`` / ``rcs_domain='delta'``
store an amplitude ``A`` that already is physical (physical power ``|A|**2``).
The native decoder converts them to standard samples once; feature placement
accepts any compatible response without a delta tag or declaration.
"""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(REPO), str(REPO / "tools/GHOST"), str(REPO / "tools/GHOST/ghost_backend")]
import ghost_backend.assembly.fields as fs  # noqa: E402
from ghost_backend.data_tools.cem_tools import native_samples  # noqa: E402
from ghost_backend.data_tools.cem_tools.grim_native import subtract_payloads  # noqa: E402
from ghost_backend.io import naming  # noqa: E402
from test_point_scatter_physics import _write_point_grim  # noqa: E402

C0 = 299_792_458.0
FREQUENCIES = np.array([1.0, 2.0])
SHAPE = (4, 1, 2, 2)
UNITS = {
    "sigma_3d": {"azimuth": "deg", "elevation": "deg", "frequency": "GHz",
                 "rcs_linear_quantity": "sigma_3d", "rcs_log_unit": "dBsm"},
    "sigma_2d": {"azimuth": "deg", "elevation": "deg", "frequency": "GHz",
                 "rcs_linear_quantity": "sigma_2d", "rcs_log_unit": "dBke"},
}


def _amplitude(seed=5):
    rng = np.random.default_rng(seed)
    return (rng.normal(size=SHAPE) + 1j * rng.normal(size=SHAPE)) * 0.4


def _legacy_payload(layout, quantity, amplitude):
    data = dict(azimuths=np.arange(4.0) * 10.0, elevations=np.array([0.0]),
                frequencies=FREQUENCIES, polarizations=np.asarray(["VV", "HH"]),
                units=json.dumps(UNITS[quantity]), power_domain="delta_amp_sq",
                rcs_domain="delta", history="legacy ghost delta", source_path="")
    if layout == "c":
        data.update(grim_format_version=np.int16(2), storage_kind="complex",
                    storage_domain="raw_field", rcs_complex=amplitude)
    else:
        data.update(rcs_power=np.abs(amplitude) ** 2, rcs_phase=np.angle(amplitude))
        if layout == "b":
            data.update(rcs_amp_real=amplitude.real, rcs_amp_imag=amplitude.imag,
                        raw_complex_amplitude_preserved=True)
    return data


def _write(path, data):
    with Path(path).open("wb") as stream:
        np.savez(stream, **data)
    return str(path)


def _physical_power(decoded):
    scale = np.asarray(fs.convention_scale(decoded), dtype=float)
    factor = scale[None, None, :, None] if scale.size > 1 else float(scale.ravel()[0])
    return np.abs(np.asarray(decoded["_amp"]) * factor) ** 2


def _physical_2d_delta(path, amplitude, **extra):
    """A featured-minus-clean 2-D response with standard tags only."""
    k = 2.0 * math.pi * 2.0e9 / C0
    payload = {
        "azimuths": np.asarray([0.0, 90.0, 180.0]),
        "elevations": np.asarray([0.0]),
        "frequencies": np.asarray([2.0]),
        "polarizations": np.asarray(["VV", "HH"]),
        "rcs_power": (np.abs(amplitude) ** 2 / (4.0 * k)),
        "rcs_phase": np.angle(amplitude),
        "power_domain": "linear_rcs",
        "units": json.dumps(UNITS["sigma_2d"]),
        "phase_reference": fs.PHYSICAL_2D_PHASE_REFERENCE,
        "amplitude_convention": fs.PHYSICAL_2D_AMPLITUDE_CONVENTION,
        "complex_field_domain": fs.PHYSICAL_2D_FIELD_DOMAIN,
        "time_convention": "exp(+jwt)",
        "amplitude_version": 2,
        "raw_complex_amplitude_preserved": True,
        "rcs_amp_real": amplitude.real,
        "rcs_amp_imag": amplitude.imag,
    }
    payload.update(extra)
    return _write(path, payload)


class LegacyDeltaConversionTests(unittest.TestCase):
    def test_three_layouts_two_quantities_decode_to_physical_amplitude_squared(self):
        amplitude = _amplitude()
        with tempfile.TemporaryDirectory() as directory:
            for quantity in ("sigma_3d", "sigma_2d"):
                for layout in "abc":
                    with self.subTest(layout=layout, quantity=quantity):
                        path = _write(Path(directory) / f"{layout}_{quantity}.grim",
                                      _legacy_payload(layout, quantity, amplitude))
                        decoded = fs._load_grim(path)
                        np.testing.assert_allclose(_physical_power(decoded), np.abs(amplitude) ** 2,
                                                   rtol=1e-12)
                        np.testing.assert_allclose(np.asarray(decoded["rcs_power"], float),
                                                   np.abs(amplitude) ** 2, rtol=1e-12)
                        self.assertEqual(str(decoded["power_domain"]), "linear_rcs")
                        self.assertNotEqual(str(decoded["rcs_domain"]), "delta")
                        self.assertIn(native_samples.LEGACY_DELTA_HISTORY_NOTE, str(decoded["history"]))

    def test_sample_reader_converts_the_same_way(self):
        amplitude = _amplitude()
        with tempfile.TemporaryDirectory() as directory:
            for layout in "abc":
                with self.subTest(layout=layout):
                    path = _write(Path(directory) / f"{layout}.grim",
                                  _legacy_payload(layout, "sigma_2d", amplitude))
                    sample = fs._load_grim_sample(path, 2.0, 20.0, 0.0)
                    np.testing.assert_allclose(_physical_power(sample).ravel(),
                                               np.abs(amplitude[2, 0, 1, :]) ** 2, rtol=1e-12)

    def test_conversion_is_idempotent_and_leaves_ordinary_payloads_alone(self):
        amplitude = _amplitude()
        once = native_samples.convert_legacy_delta(_legacy_payload("b", "sigma_3d", amplitude))
        twice = native_samples.convert_legacy_delta(once)
        self.assertIs(twice, once)
        ordinary = {"rcs_domain": "power_phase", "power_domain": "linear_rcs"}
        self.assertIs(native_samples.convert_legacy_delta(ordinary), ordinary)

    def test_in_memory_payload_tags_no_longer_change_the_scale(self):
        payload = {"power_domain": "delta_amp_sq", "rcs_domain": "delta",
                   "units": json.dumps(UNITS["sigma_3d"])}
        np.testing.assert_allclose(fs.convention_scale(payload), math.sqrt(4.0 * math.pi))
        _units, scale = native_samples.units_and_scale(payload)
        np.testing.assert_allclose(scale, math.sqrt(4.0 * math.pi))


class NoDeltaGateTests(unittest.TestCase):
    def setUp(self):
        self.amplitude = np.array([[1 + 2j, -0.5 + 1j]] * 3).reshape(3, 1, 1, 2) * 1e-2

    def test_seam_response_without_tag_or_declaration_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _physical_2d_delta(Path(directory) / "seam_OPN.grim", self.amplitude)
            plain = fs.load_seam_from_grim(path, 2.0)
            declared = fs.load_seam_from_grim(path, 2.0, declared_coherent_delta=True)
            np.testing.assert_array_equal(plain.dA_te, self.amplitude[:, 0, 0, 0])
            np.testing.assert_array_equal(plain.dA_tm, self.amplitude[:, 0, 0, 1])
            np.testing.assert_array_equal(declared.dA_te, plain.dA_te)

    def test_legacy_delta_markers_read_as_the_physical_convention(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _physical_2d_delta(
                Path(directory) / "legacy.grim", self.amplitude, rcs_domain="delta",
                phase_reference=fs.PHYSICAL_2D_PHASE_REFERENCE + fs.DELTA_PHASE_SUFFIX,
                complex_field_domain=fs.DELTA_FIELD_DOMAIN)
            decoded = fs._load_grim(path)
            self.assertEqual(str(decoded["phase_reference"]), fs.PHYSICAL_2D_PHASE_REFERENCE)
            self.assertEqual(str(decoded["complex_field_domain"]), fs.PHYSICAL_2D_FIELD_DOMAIN)
            self.assertNotEqual(str(decoded["rcs_domain"]), "delta")
            for kind in ("delta", "object", ""):
                with self.subTest(kind=kind):
                    coefficient = (fs.load_coefficients_from_grim(path, 2.0) if kind == "object"
                                   else fs.load_seam_from_grim(path, 2.0))
                    np.testing.assert_array_equal(coefficient.dA_te, self.amplitude[:, 0, 0, 0])

    def test_point_pattern_without_tag_or_declaration_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "point_FRD.grim"
            _write_point_grim(path, np.eye(3), [1.0])
            with np.load(path, allow_pickle=False) as archive:
                payload = {key: archive[key] for key in archive.files}
            payload.pop("rcs_domain")
            _write(path, payload)
            plain = fs.prepare_point_pattern(str(path))
            declared = fs.prepare_point_pattern(str(path), declared_coherent_delta=True)
            np.testing.assert_array_equal(plain.amplitude, declared.amplitude)
            payload["rcs_domain"] = "power_phase"
            _write(path, payload)
            np.testing.assert_array_equal(fs.prepare_point_pattern(str(path)).amplitude, plain.amplitude)

    def test_power_phase_only_point_pattern_is_accepted_without_declaration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "point.grim"
            _write_point_grim(path, np.eye(3), [1.0])
            with np.load(path, allow_pickle=False) as archive:
                payload = {key: archive[key] for key in archive.files}
            for key in ("rcs_amp_real", "rcs_amp_imag", "raw_complex_amplitude_preserved", "rcs_domain"):
                payload.pop(key)
            _write(path, payload)
            pattern = fs.prepare_point_pattern(str(path))
            self.assertTrue(np.all(np.isfinite(pattern.amplitude)))

    def test_physics_checks_remain(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _physical_2d_delta(Path(directory) / "wrong.grim", self.amplitude,
                                      time_convention="exp(-jwt)")
            with self.assertRaisesRegex(ValueError, "time_convention"):
                fs.load_seam_from_grim(path, 2.0)
            path = _physical_2d_delta(Path(directory) / "units.grim", self.amplitude,
                                      units=json.dumps(UNITS["sigma_3d"]))
            with self.assertRaises(ValueError):
                fs.load_seam_from_grim(path, 2.0)

    def test_deprecated_helpers_never_block(self):
        self.assertEqual(naming.require_role_free_declared_delta("SEAL-00-01_0.010gap_OPN.grim"),
                         "SEAL-00-01_0.010gap")
        for domain in ("delta", "linear_rcs", "power_phase", ""):
            metadata = {"rcs_domain": domain} if domain else {}
            self.assertIsInstance(fs.validate_declared_coherent_delta_domain(metadata, "x"), str)
        with tempfile.TemporaryDirectory() as directory:
            path = _physical_2d_delta(Path(directory) / "t.grim", self.amplitude)
            before = Path(path).read_bytes()
            self.assertEqual(fs.tag_as_delta(path), path)
            self.assertEqual(Path(path).read_bytes(), before)

    def test_producers_write_standard_tags(self):
        rng = np.random.default_rng(2)
        shape = (3, 1, 1, 2)
        featured = rng.normal(size=shape) + 1j * rng.normal(size=shape)
        clean = rng.normal(size=shape) + 1j * rng.normal(size=shape)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, value in (("clean", clean), ("featured", featured)):
                _physical_2d_delta(root / f"{name}.grim", value, rcs_domain="power_phase")
            out = fs.make_delta_grim(str(root / "clean.grim"), str(root / "featured.grim"),
                                     str(root / "delta.grim"))
            with np.load(out, allow_pickle=False) as archive:
                self.assertEqual(str(archive["power_domain"]), "linear_rcs")
                self.assertNotEqual(str(archive["rcs_domain"]), "delta")
                self.assertEqual(str(archive["complex_field_domain"]), fs.PHYSICAL_2D_FIELD_DOMAIN)
                self.assertEqual(str(archive["phase_reference"]), fs.PHYSICAL_2D_PHASE_REFERENCE)
            np.testing.assert_allclose(fs.load_seam_from_grim(out, 2.0).dA_te,
                                       (featured - clean)[:, 0, 0, 0])
            payloads = {name: dict(np.load(root / f"{name}.grim", allow_pickle=False))
                        for name in ("clean", "featured")}
        result = subtract_payloads(payloads["featured"], payloads["clean"],
                                   featured_label="featured", clean_label="clean")
        self.assertEqual(str(result["rcs_domain"]), "power_phase")
        self.assertEqual(str(result["power_domain"]), "linear_rcs")
        self.assertNotIn(fs.DELTA_PHASE_SUFFIX, str(result.get("phase_reference", "")))
        self.assertNotEqual(str(result.get("complex_field_domain", "")), fs.DELTA_FIELD_DOMAIN)


if __name__ == "__main__":
    unittest.main()
