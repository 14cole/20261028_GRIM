import numpy as np
from unittest.mock import patch

from ibc.compute import C0, ConstantMaterial, LoadedLayer, UncertaintyConfig, compute_stack_impedance_many
from ibc.uncertainty import impedance_envelope
from ibc.analysis_data import impedance_result


def layer():
    return [LoadedLayer(C0/(4*10e9*2)/1.0125, False, 0,
                        ConstantMaterial(4-.002j, 1+0j), None)]


def test_narrow_resonance_between_seed_points_is_refined():
    layers = layer()
    result = impedance_envelope([10.], layers, 'pec', UncertaintyConfig(True, 10, 0, 0))
    # Independent dense samples in the narrow resonant neighborhood, not the
    # same optimizer or the old nine seed points.
    reference = np.array([compute_stack_impedance_many([10.], layers, 'pec', thickness_scale=t)[0]
                          for t in np.linspace(1.0115, 1.0135, 2001)])
    bounds = result['impedance_bounds']
    assert bounds['real_max'][0] >= .999 * reference.real.max()
    assert bounds['imag_max'][0] >= .999 * reference.imag.max()
    assert bounds['imag_min'][0] <= .999 * reference.imag.min()
    assert result['budget_exhausted_frequencies'] == 0
    assert result['unconverged_searches'] == 0
    assert 'not a certified bound' in result['note']


def test_refinement_budget_is_bounded_and_reported():
    with patch('ibc.uncertainty.MAX_REFINEMENT_EVALUATIONS', 2):
        result = impedance_envelope([10.], layer(), 'pec', UncertaintyConfig(True, 10, 0, 0))
    assert result['refinement_evaluations'] == 2
    assert result['budget_exhausted_frequencies'] == 1
    assert 'Refinement incomplete' in result['note']


def test_disabled_uncertainty_and_captured_plot_envelope():
    layers = layer()
    nominal = compute_stack_impedance_many([10.], layers, 'pec')
    result = impedance_envelope([10.], layers, 'pec', UncertaintyConfig(False, 10, 0, 0), nominal)
    assert result['refinement_evaluations'] == 0
    assert result['impedance_bounds']['real_max'][0] == nominal[0].real
    capture = dict(nominal=nominal, cases=[nominal], **result)
    capture['impedance_bounds']['real_max'] = np.array([12345.])
    capture['reflection_bounds'] = (np.array([-20.]), np.array([-1.]))
    plotted = impedance_result([10.], capture, {}, 'pec', 'test')
    assert plotted.impedance_bounds['real_max'][0] == 12345.
    assert plotted.upper['TE']['metal_loss_db'][0, 0] == -1.
