"""Channel score medians average central power ratios before dB conversion."""
import numpy as np
import pytest

from GRIM_Backend.plotting.analysis_results import AnalysisOptions, polarization_analysis
from GRIM_Backend.plotting.engineering_tools import EngineeringCut, channel_comparison


def _cut(power, label):
    power = np.asarray(power, dtype=float)
    x = np.arange(len(power), dtype=float) + 9.
    with np.errstate(divide="ignore", invalid="ignore"):
        field = np.sqrt(power).astype(complex)
        db = 10. * np.log10(power)
    return EngineeringCut(x, power, field, db, "frequency", "GHz", "dBsm", label,
                          "+jwt", [], "sigma_3d", label, {}, np.arange(len(power)))


def _result(left, right, options=None, view="ratios"):
    return polarization_analysis({"HH": left, "VV": right}, [("HH", "VV")], view,
                                 options or AnalysisOptions(), fallback=left)


def _median(result):
    return next(value for name, value, unit in result.rows if name == "HH / VV median")


@pytest.mark.parametrize("ratios,expected", [([1., 100.], 50.5), ([100., 1.], 50.5),
                                           ([1., 4., 16., 100.], 10.), ([1., 100., 10000.], 100.)])
def test_polarization_median_uses_linear_power_ratios(ratios, expected):
    left, right = _cut(ratios, "HH"), _cut(np.ones(len(ratios)), "VV")
    result = _result(left, right)
    assert float(_median(result)) == pytest.approx(10. * np.log10(expected))
    np.testing.assert_allclose(result.traces[-1].y, 10. * np.log10(ratios))
    assert "median of linear power ratios" in next(unit for name, value, unit in result.rows if name.endswith(" median"))


@pytest.mark.parametrize("ratios,expected", [([0., 100.], 50.), ([0., 0.], 0.), ([0., 0., 100.], 0.)])
def test_valid_zero_ratios_contribute_when_magnitude_mask_is_disabled(ratios, expected):
    result = _result(_cut(ratios, "HH"), _cut(np.ones(len(ratios)), "VV"), AnalysisOptions(floor_db=None))
    actual = float(_median(result))
    assert actual == (-np.inf if expected == 0. else pytest.approx(10. * np.log10(expected)))
    count = next(value for name, value, unit in result.rows if name == "HH / VV valid samples")
    assert int(count) == len(ratios)


def test_region_and_magnitude_mask_still_define_polarization_population():
    left = _cut([1.e-8, 1., 100., 1.e8], "HH")
    right = _cut([1., 1., 1., 1.], "VV")
    result = _result(left, right, AnalysisOptions(region=(9., 11.)))
    assert float(_median(result)) == pytest.approx(10. * np.log10(50.5))
    np.testing.assert_array_equal(np.isnan(result.traces[-1].y), [True, False, False, True])


def test_extreme_power_ratios_do_not_overflow_linear_median_conversion():
    # The physical ratios exceed float64, but their dB score is still defined.
    left, right = _cut([1.e300, 1.e300], "HH"), _cut([1.e-300, 1.e-299], "VV")
    result = _result(left, right)
    assert float(_median(result)) == pytest.approx(6000. + 10. * np.log10(.55))


def test_phase_diagnostics_and_undefined_ratio_remain_unchanged():
    left, right = _cut([1., 100.], "HH"), _cut([1., 1.], "VV")
    left.field *= np.exp(1j * np.deg2rad(30.))
    report = channel_comparison(left, right)
    result = _result(left, right, view="phase")
    np.testing.assert_allclose(result.traces[-1].y, 30.)
    assert not any(name.endswith(" median") for name, value, unit in result.rows)
    mismatch = next(value for name, value, unit in result.rows if name.endswith(" normalized complex mismatch"))
    assert float(mismatch) == pytest.approx(report["normalized_complex_mismatch"])
    undefined = _result(left, _cut([0., 0.], "VV"))
    assert _median(undefined) == "not defined"
