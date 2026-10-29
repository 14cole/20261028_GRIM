"""Range-phase declarations determine coordinates before power-only imaging."""
from unittest import mock

import numpy as np
import pytest

from GRIM_Backend.datasets.constants import C0
from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.plotting.modes import range_freq_mode as rf
from GRIM_Backend.plotting.requests import PlotPlan, PlotRequest


def point_dataset(range_sign, time_sign, target=.6, *, declared=True):
    frequency = np.linspace(8.e9, 12.e9, 129)
    field = 2 * np.exp(range_sign * 4j * np.pi * frequency * target / C0)
    units = {'frequency': 'Hz', 'azimuth': 'deg', 'elevation': 'deg'}
    if time_sign is not None:
        units['time_convention'] = f'exp({time_sign}jwt)'
    extra = ({'range_phase_convention': f'exp({"+" if range_sign > 0 else "-"}j2kR)'}
             if declared else {})
    return RcsGrid([0.], [0.], frequency, ['VV'], rcs=field[None, None, :, None],
                   units=units, extra=extra)


def request_for(*datasets):
    plans = tuple(PlotPlan(f'point {index}', dataset,
        ([0], [0], np.arange(len(dataset.frequencies)), [0]))
        for index, dataset in enumerate(datasets))
    return PlotRequest('range_freq', datasets[0], plans, scale='linear',
        options={'percent': 25., 'window': 'Rectangular', 'unit': 'm'})


@pytest.mark.parametrize('target', [-.6, .6])
@pytest.mark.parametrize('range_sign', [-1, 1])
@pytest.mark.parametrize('time_sign', ['+', '-', None])
def test_explicit_range_law_sets_coordinate_independently_of_time(target, range_sign, time_sign):
    dataset = point_dataset(range_sign, time_sign, target)
    before = dataset.rcs_slice((slice(None),) * 4).copy()
    result = rf.prepare_range_frequency(request_for(dataset))
    try:
        assert not result.skipped
        panel = result.items[0]
        peaks = np.argmax(panel['image'], axis=1)
        np.testing.assert_allclose(panel['y'][peaks], target, atol=.04)
        np.testing.assert_allclose(np.max(panel['image'], axis=1), 4., rtol=.02)
        assert panel['phase_normalization']['conjugated'] == (range_sign == 1)
        assert result.notes and 'declared exp(' in result.notes[0]
        np.testing.assert_array_equal(dataset.rcs_slice((slice(None),) * 4), before)
    finally:
        result.close()


@pytest.mark.parametrize('range_sign,time_sign', [(-1, '+'), (1, '-'), (-1, None)])
def test_missing_range_law_retains_time_convention_fallback(range_sign, time_sign):
    dataset = point_dataset(range_sign, time_sign, declared=False)
    result = rf.prepare_range_frequency(request_for(dataset))
    try:
        panel = result.items[0]
        np.testing.assert_allclose(panel['y'][np.argmax(panel['image'], axis=1)], .6, atol=.04)
        assert panel['phase_normalization']['range_phase_sign'] is None
    finally:
        result.close()


@pytest.mark.parametrize('container,key,value,reason', [
    ('units', 'range_phase_convention', 'exp(-j2kR)', 'contradictory two-way range-phase'),
    ('extra', 'range_phase_convention', 'exp(+j2kR) and exp(-j2kR)', 'contradictory two-way range-phase'),
    ('extra', 'time_convention', 'exp(-jwt)', 'contradictory time'),
    ('units', 'time_convention', 'exp(+jwt) and exp(-jwt)', 'contradictory time'),
    ('extra', 'range_phase_convention', ['exp(+j2kR)', 'exp(-j2kR)'], 'must be scalar'),
])
def test_bad_declarations_skip_only_bad_dataset_before_reading_samples(container, key, value, reason):
    invalid = point_dataset(1, '+')
    getattr(invalid, container)[key] = value
    valid = point_dataset(-1, '+')
    with mock.patch.object(invalid, 'rcs_slice', side_effect=AssertionError('read bad metadata')), \
         mock.patch.object(invalid, 'phase_coverage', side_effect=AssertionError('scanned bad metadata')):
        result = rf.prepare_range_frequency(request_for(invalid, valid))
    try:
        assert len(result.items) == 1 and result.items[0]['name'] == 'point 1'
        assert len(result.skipped) == 1 and reason in result.skipped[0]
    finally:
        result.close()
