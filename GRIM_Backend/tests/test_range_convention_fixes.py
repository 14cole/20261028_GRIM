"""Signed physics checks at the GUI and worker boundaries."""
import numpy as np
import pytest
from GRIM_Backend.datasets.phase_conventions import declared_time_sign
from GRIM_Backend.plotting.modes import az_vs_range_mode as azr
from test_isar_accuracy_2026_10_17 import grid, form, AZ, F, _range_request


@pytest.mark.parametrize('container', ['units', 'extra'])
@pytest.mark.parametrize('key', ['time_convention', 'phase_reference', 'amplitude_convention'])
def test_negative_time_is_normalized_from_all_metadata_locations(container, key):
    d = grid(AZ, F, [(.3,.6,1.)], negative_time=True)
    del d.units['time_convention']
    if key == 'phase_reference':
        del d.extra['phase_reference']
    getattr(d, container)[key] = 'fixed origin; exp(-jwt)'
    band = form(d)
    reference = form(grid(AZ,F,[(.3,.6,1.)]))
    np.testing.assert_allclose(band['complex_image'],reference['complex_image'],atol=1e-7)
    result = azr.prepare_azimuth_range(_range_request(d, 'Hanning')).items[0]
    assert result['range_axis'][np.argmax(result['display'][len(AZ)//2])] == pytest.approx(.6,abs=.012)


@pytest.mark.parametrize('value', ['exp(-jwt)', 'exp(+jwt); exp(-jwt)'])
def test_conflicting_time_declarations_block_both_paths(value):
    d = grid(AZ,F,[(.3,.6,1.)])
    d.extra['amplitude_convention'] = value
    for call in (lambda: form(d), lambda: azr.prepare_azimuth_range(_range_request(d,'Hanning'))):
        with pytest.raises(ValueError,match='contradictory time'):
            call()


@pytest.mark.parametrize('key', ['range_phase_convention','phase_law','amplitude_convention','phase_reference'])
def test_positive_range_law_requires_explicit_range_mirror(key):
    d = grid(AZ,F,[(.3,.6,1.)],negative_time=True)
    d.units['time_convention'] = 'exp(+jwt)'
    del d.extra['range_phase_convention']
    d.extra[key] = 'fixed origin; S~exp(+j*2*k*R)'
    request = _range_request(d,'Hanning')
    with pytest.raises(ValueError,match='enable Flip Y'):
        azr.prepare_azimuth_range(request)
    request.options['flip_y'] = True
    result = azr.prepare_azimuth_range(request).items[0]
    assert result['range_axis'][np.argmax(result['display'][len(AZ)//2])] == pytest.approx(.6,abs=.012)


def test_negative_time_positive_range_law_is_normalized_once():
    d = grid(AZ,F,[(.3,.6,1.)],negative_time=True)
    d.extra['range_phase_convention'] = 'S~exp(+j*2*k*R)'
    result = azr.prepare_azimuth_range(_range_request(d,'Hanning')).items[0]
    assert result['range_axis'][np.argmax(result['display'][len(AZ)//2])] == pytest.approx(.6,abs=.012)


def test_range_metadata_conflicts_are_rejected_even_with_mirror():
    d = grid(AZ,F,[(.3,.6,1.)])
    d.extra['phase_law'] = 'S~exp(+j*2*k*R)'
    request = _range_request(d,'Hanning')
    request.options['flip_y'] = True
    with pytest.raises(ValueError,match='contradictory two-way'):
        azr.prepare_azimuth_range(request)


def test_malformed_time_declaration_cannot_be_treated_as_missing():
    d = grid(AZ,F)
    d.extra['time_convention'] = ['exp(+jwt)','exp(-jwt)']
    with pytest.raises(ValueError,match='must be scalar'):
        declared_time_sign(d)


@pytest.mark.parametrize('value', ['-jwt', 'exp(-j*omega*t)', 'exp(−jωt)'])
def test_supported_negative_time_spellings(value):
    d = grid(AZ,F)
    d.units['time_convention'] = value
    assert declared_time_sign(d) == '-jwt'
