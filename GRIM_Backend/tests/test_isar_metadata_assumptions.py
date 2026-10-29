"""Known signed targets verify normalization, assumptions, and retained rejection checks."""
import copy
import numpy as np
import pytest
from test_isar_accuracy_2026_10_17 import grid, form, AZ, F, field
from GRIM_Backend.plotting.modes import isar_mode as isar
from GRIM_Backend.isar.artifact import build_isar_manifest, save_isar_artifact, load_isar_artifact


@pytest.mark.parametrize('reconstruction',['fast','accurate','auto'])
@pytest.mark.parametrize('range_sign',[-1,1])
def test_negative_time_matches_complex_image_and_native_residual(reconstruction,range_sign):
    samples = field(AZ,F,[(.3,.6,1.),(-.4,-.7,.2)]) * np.exp(.7j)
    positive = grid(AZ,F,samples=samples)
    negative = grid(AZ,F,samples=samples,negative_time=True)
    negative.extra['range_phase_convention'] = f'S~exp({"+" if range_sign==1 else "-"}j*2*k*R)'
    before = negative.rcs_slice((slice(None),0,slice(None),0)).copy()
    metadata = copy.deepcopy((negative.units,negative.extra))
    expected = form(positive,reconstruction=reconstruction)
    for repeat in range(2):
        actual = form(negative,reconstruction=reconstruction)
        np.testing.assert_allclose(actual['complex_image'],expected['complex_image'],atol=1e-7)
        np.testing.assert_array_equal(actual['x_range'],expected['x_range'])
        np.testing.assert_array_equal(actual['y_range'],expected['y_range'])
        assert actual['time_convention_conjugated']
        assert actual['image_contract']['processing_time_convention']=='+jwt'
        if repeat:
            assert actual['preprocess_cache_hit']
    np.testing.assert_array_equal(before,negative.rcs_slice((slice(None),0,slice(None),0)))
    assert (negative.units,negative.extra)==metadata


def test_negative_time_composite_matches_and_retains_normalization():
    az=np.linspace(-25.,25.,151)
    positive=grid(az,F,[(.3,.6,1.)])
    negative=grid(az,F,[(.3,.6,1.)],negative_time=True)
    opts=dict(aperture_mode='composite',composite_side=128,scene_half_extent_m=(1.,1.))
    a,b=form(positive,**opts),form(negative,**opts)
    np.testing.assert_allclose(a['magnitude'],b['magnitude'],atol=1e-7)
    assert b['image_contract']['time_convention_conjugated']


@pytest.mark.parametrize('key,assumption',[
    ('phase_reference','a fixed phase reference/center'),
    ('measurement_geometry','far-field monostatic acquisition geometry'),
    ('motion_compensation','a stable or motion-compensated phase center'),
    ('time_convention','the exp(+j*omega*t) time convention'),
    ('range_phase_convention','the S~exp(-j*2*k*R) two-way range-phase convention'),
    ('elevation_coordinate_convention','GRIM signed elevation coordinates'),
])
@pytest.mark.parametrize('placeholder',[None,'','none','unknown','unspecified','N/A','arbitrary'])
def test_placeholder_is_assumption_not_blocker(key,assumption,placeholder):
    d=grid(AZ,F,[(.3,.6,1.)])
    d.units.pop(key,None)
    d.extra.pop(key,None)
    d.units[key]=placeholder
    d.extra[key]='unknown'
    b=form(d)
    assert assumption in b['isar_contract_undeclared_fields']
    assert b['magnitude'].max()>.8


def test_unknown_elevation_label_and_empty_bistatic_marker_are_assumptions():
    d=grid(AZ,F,[(.3,.6,1.)])
    d.units['elevation_coordinate_convention']='vendor unspecified axes'
    d.extra['fixed_incident_azimuth_deg']=None
    b=form(d)
    assert 'GRIM signed elevation coordinates' in b['isar_contract_undeclared_fields']
    d.extra['fixed_incident_azimuth_deg']=0.
    assert any('bistatic acquisition' in note for note in form(d)['isar_metadata_notes'])


def test_placeholder_does_not_conflict_with_real_reference():
    d=grid(AZ,F,[(.3,.6,1.)])
    d.units['phase_reference']='unknown phase reference'
    assert 'a fixed phase reference/center' not in form(d)['isar_contract_undeclared_fields']


@pytest.mark.parametrize('other',['vendor convention unknown','exp(+j*omega*t)'])
def test_unknown_or_equivalent_time_label_does_not_conflict(other):
    d=grid(AZ,F,[(.3,.6,1.)])
    d.extra['time_convention']=other
    assert not form(d)['time_convention_conjugated']


def test_unknown_elevation_label_does_not_conflict_with_known_signed_axes():
    d=grid(AZ,F,[(.3,.6,1.)])
    d.units['elevation_coordinate_convention']='grim_elevation_waterline_zero_top_positive'
    d.extra['sentri_elevation_convention']='vendor convention unknown'
    assert 'GRIM signed elevation coordinates' not in form(d)['isar_contract_undeclared_fields']


def test_complex_export_preserves_normalization_contract(tmp_path):
    d=grid(AZ,F,[(.3,.6,1.)],negative_time=True)
    b=form(d)
    params=dict(bands=[list(range(len(AZ)))],freq_indices_sorted=list(range(len(F))),
        freq_hz=F,elev_idx=0,elevation_deg=0,pol_idx=0,recon='fft',window_name='Hanning',
        unit_name='m',az_target_deg=None,az_center_deg=None,l1_strength=.05,l1_iters=300,
        flip_x=False,flip_y=False,isar_contract_assumptions=b['isar_contract_undeclared_fields'])
    manifest=build_isar_manifest(d,params,[b],0.)
    path=save_isar_artifact(tmp_path/'negative_time',[b],manifest)
    restored, bands=load_isar_artifact(path)
    contract=restored['bands'][0]['image_contract']
    assert contract['source_time_convention']=='-jwt'
    assert contract['processing_time_convention']=='+jwt'
    assert contract['time_convention_conjugated']
    np.testing.assert_array_equal(bands[0]['complex_image'],b['complex_image'])
