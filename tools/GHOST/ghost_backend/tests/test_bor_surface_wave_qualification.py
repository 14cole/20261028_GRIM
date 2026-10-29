"""Reactive BoR certificates must resolve both guided-current branches."""
import math
from pathlib import Path
import sys
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghost_backend.bor import dispatch as d, solver as b
from ghost_backend.bor.surface_waves import direct_surface_wave_sampling, surface_wave_indices
from ghost_backend.bor.kernels import C0, ETA0
from ghost_backend.twod.geometry import MaterialLibrary

OPTIONS = dict(factorization='dense')


def sheet(z=1000j, n=0, radius=.15):
    return dict(segments=[dict(name='reactive_disk',seg_type=1,
        properties=['1',str(n),'1','0','0'],
        point_pairs=[dict(x1=0.,y1=0.,x2=radius,y2=0.)])],dielectrics=[],
        ibcs=[['1','constant',str(z.real),str(z.imag),'0','0']])


def prepare(snapshot, frequency=1.):
    materials=MaterialLibrary.from_entries(snapshot['ibcs'], [], '.')
    chains=d._chains_from_snapshot(snapshot,1.)
    kind=d._classify(chains)
    groups, _, axis_tol=d._prepare_bor_groups(chains,kind)
    wave=C0/(frequency*1.e9)
    d._configure_surface_wave_mesh(chains,materials,[frequency],wave)
    return chains, d._surface_wave_sampling(groups,kind,materials,frequency,wave,axis_tol,10000)


def test_two_sided_sheet_dispersion_checks_both_current_families():
    # Independent planar dispersion: positive reactance has longitudinal
    # electric-current kappa/k0=2X/eta; negative has transverse -eta/(2X).
    actual=surface_wave_indices([1000j,-30j,0j],transmitting_sheet=True)
    np.testing.assert_allclose(actual,[math.sqrt(1+(2000/ETA0)**2),
                                     math.sqrt(1+(ETA0/60)**2),0.],rtol=1.e-14)
    opaque=surface_wave_indices([1000j,-30j])
    np.testing.assert_allclose(opaque,[math.sqrt(1+(1000/ETA0)**2),
                                     math.sqrt(1+(ETA0/30)**2)],rtol=1.e-14)


@pytest.mark.parametrize('z',[1000j,-30j,20+1000j,20-30j])
def test_automatic_mesh_resolves_each_supported_local_branch(z):
    chains,report=prepare(sheet(z))
    assert report['resolved']
    assert report['segments'][0]['samples_per_wavelength'] >= 20.
    assert chains[0].surface_wave_wavelength < C0/1.e9


def test_automatic_cap_and_explicit_counts_cannot_hide_underresolution(monkeypatch):
    calls=[]
    monkeypatch.setattr(d,'solve_bor',lambda *a,**k: calls.append(k))
    for shape in [sheet(10000j),sheet(1000j,n=10),sheet(-1j)]:
        with pytest.raises(ValueError,match='unresolved bound surface-wave sampling.*base mesh'):
            d.solve_monostatic_rcs_bor_certified(shape,[1.],[0.,37.],
                geometry_units='meters',workers=2,bor_options=OPTIONS)
    assert calls == []


def test_modal_floor_includes_a_late_guided_band_and_preserves_exact_axial_case():
    cap,tail=b._bor_mode_limits(20.,.15,[37.],None,surface_wave_bandwidth=167.2)
    assert tail == 168 and cap > tail+2
    with pytest.raises(ValueError,match='cannot cover the bound surface-wave band'):
        b._bor_mode_limits(20.,.15,[37.],18,surface_wave_bandwidth=167.2)
    assert b._bor_mode_limits(20.,.15,[0.,180.],None,surface_wave_bandwidth=167.2) == (1,1)


def test_actual_panel_sampling_uses_local_radius_and_element_lengths():
    pts=np.array([[0.,0.],[.01,0.],[.1,0.]])
    report=direct_surface_wave_sampling(pts,[1000j,0.],1.e9,transmitting_sheet=True)
    index=math.sqrt(1+(2000/ETA0)**2)
    assert report['surface_wave_mode_bandwidth'] == pytest.approx(2*np.pi*1.e9/C0*index*.01)
    assert report['samples_per_wavelength'] == pytest.approx(C0/1.e9/index/.01)
    assert not report['resolved']


def test_resource_gate_precedes_sampling_mesh_allocation(monkeypatch):
    calls=[]
    monkeypatch.setattr(d,'_mesh_generatrix',lambda *a,**k:calls.append(a))
    with pytest.raises(ValueError,match='elements'):
        d.estimate_bor_resources(sheet(),1.,[37.],geometry_units='meters',
                                max_elements=10,bor_options=OPTIONS)
    assert calls == []


def test_preview_and_solve_price_the_same_guided_modes_and_mesh():
    shape=sheet(1000j)
    preview=d.estimate_bor_resources(shape,1.,[0.,37.,90.],geometry_units='meters',
                                    mesh_certification=False,workers=2,bor_options=OPTIONS)
    result=d.solve_monostatic_rcs_bor(shape,[1.],[0.,37.,90.],geometry_units='meters',
                                    workers=2,bor_options=OPTIONS)
    row=result['metadata']['per_frequency'][0]
    assert row['surface_wave_sampling']['resolved']
    assert row['mesh_elements_total'] == preview['mesh_elements']
    assert row['mode_tail_start'] == preview['mode_tail_start_estimate']
    assert row['mode_cap'] == preview['mode_cap_estimate']
    assert row['mode_tail_start'] >= math.ceil(row['surface_wave_sampling']['surface_wave_mode_bandwidth'])
    assert row['mode_converged']


def test_direct_planner_prices_surface_wave_floor(monkeypatch):
    pts=np.column_stack((np.linspace(0.,.15,60),np.zeros(60)))
    calls=[]
    def plan(supplied,layout,modes,order):
        calls.append(modes)
        return dict(fits_memory=True)
    monkeypatch.setattr(d,'_direct_dense_plan',plan)
    d._resolve_direct_plan(dict(points=pts,freq_hz=1.e9,thetas_deg=[37.],sheet_zs=1000j))
    band=direct_surface_wave_sampling(pts,1000j,1.e9,transmitting_sheet=True)['surface_wave_mode_bandwidth']
    expected=b._bor_mode_limits(2*np.pi*1.e9/C0,.15,[37.],None,surface_wave_bandwidth=band)[0]
    assert calls == [expected]


def test_cancellation_precedes_surface_law_loop():
    import threading
    abort=threading.Event()
    abort.set()
    with pytest.raises(InterruptedError):
        d.solve_monostatic_rcs_bor_certified(sheet(),[1.],[0.],geometry_units='meters',
            abort_event=abort,bor_options=OPTIONS)


@pytest.mark.parametrize('values',[[1j],[[1j],[2j]],[np.nan*1j,1j],[np.inf*1j,1j]])
def test_direct_planner_rejects_invalid_sheet_arrays(values):
    with pytest.raises(ValueError,match='one value per|finite'):
        d._resolve_direct_plan(dict(points=[[0.,0.],[.01,0.],[.02,0.]],
            freq_hz=1.e9,thetas_deg=[37.],sheet_zs=values))


def test_taper_endpoints_and_material_table_frequency_are_measured():
    from ghost_backend.twod.geometry import ComplexTable
    shape=sheet()
    shape['ibcs']=[['1','linear','0','100','0','1000']]
    _chains,report=prepare(shape)
    expected=math.sqrt(1+(2000/ETA0)**2)
    assert report['segments'][0]['phase_index'] == pytest.approx(expected)
    shape['ibcs']=[['1','linear','0','1000','0','100']]
    _,reverse_report=prepare(shape)
    assert reverse_report['segments'][0]['phase_index'] == pytest.approx(expected)
    library=MaterialLibrary({1:ComplexTable(np.array([1.,2.]),np.array([100j,1000j]))},{})
    chains=d._chains_from_snapshot(shape,1.)
    d._configure_surface_wave_mesh(chains,library,[1.],C0/1.e9)
    low=chains[0].surface_wave_wavelength
    d._configure_surface_wave_mesh(chains,library,[2.],C0/2.e9)
    assert chains[0].surface_wave_wavelength < low/5


def test_taper_checks_actual_centers_beyond_the_nine_planning_samples(monkeypatch):
    shape=sheet(n=3)
    library=MaterialLibrary.from_entries(shape['ibcs'],[],'.')
    original=library.get_impedance
    def sharp(flag,freq,arc_s=None):
        return 10000j if arc_s is not None and .45 < arc_s < .55 else original(flag,freq,arc_s)
    monkeypatch.setattr(library,'get_impedance',sharp)
    from ghost_backend.twod import geometry as g
    monkeypatch.setattr(g,'_segment_surface_wave_index',lambda *a,**k:0.)
    chains=d._chains_from_snapshot(shape,1.)
    groups,_,tol=d._prepare_bor_groups(chains,'sheet')
    report=d._surface_wave_sampling(groups,'sheet',library,1.,C0/1.e9,tol,100)
    assert report['segments'][0]['phase_index'] > 50.
    assert not report['resolved']


def test_partial_direct_planner_counts_guided_bare_ibc_modes(monkeypatch):
    pts=np.array([[0.,.01],[.01,0.],[0.,-.01]])
    calls=[]
    monkeypatch.setattr(d,'_direct_dense_plan',lambda supplied,layout,modes,order:
                        calls.append(modes) or dict(fits_memory=True))
    supplied=dict(points_interface=pts,points_covered=pts,bare_pieces=[pts],
                  freq_hz=1.e9,thetas_deg=[37.],eps_r=2.,bare_zs=[10+10000j])
    d._resolve_direct_plan(supplied)
    band=direct_surface_wave_sampling(pts,10+10000j,1.e9)['surface_wave_mode_bandwidth']
    assert calls == [b._bor_mode_limits(2*np.pi*1.e9/C0,.01,[37.],None,
                                      surface_wave_bandwidth=band)[0]]
