"""Proposed regression cases for the Line Expansion fixes.

They state required behaviour, not one implementation: where a fix may either
refuse an input or handle it, both are accepted; a silent wrong field is not.
Real section solver, real files, every result reopened from disk.

    GRIM_ROOT=/path/to/checkout QT_QPA_PLATFORM=offscreen python -m pytest -q test_line_expansion_regressions.py

History: at ed90b65, 22 of the first 30 cases fail and 8 pass (controls). The
cases below the "acceptance" marker were added with the fix and follow Codex's
notes on f920c8a. With the fix on this branch all cases pass.
"""
import json, os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
import pytest
from common import *
from common import _save_grim_npz
from ghost_backend.geometry.occlusion import Occluder
from ghost_backend.geometry.line_visibility import visible_intervals

AZ, EL, FREQ = [0.0, 40.0, 95.0, 200.0, 310.0], [-15.0, 25.0], [1.0, 1.6]
ATT = dict(axis_az_deg=25.0, axis_el_deg=-12.0, roll_deg=40.0)
TOL = 1e-9


@pytest.fixture(scope="module")
def ctx(tmp_path_factory):
    work = tmp_path_factory.mktemp("le")
    section = write_section(work)
    grid = dict(frequencies_ghz=FREQ, azimuths_deg=AZ, elevations_deg=EL)
    ref = expand([section], output_grim=str(work/"ref.grim"), **grid)
    att = expand([section], output_grim=str(work/"att.grim"), **grid, **ATT)
    payload, field = reopen(ref["output"])
    return dict(work=work, section=section, payload=payload, ref=field,
                att_path=att["output"], att=reopen(att["output"])[1])


def write_base(ctx, name, field=None, **changes):
    field = ctx["ref"] if field is None else field
    out = {k: v for k, v in ctx["payload"].items() if not k.startswith("rcs_")or k == "rcs_domain"}
    out.update(changes)
    out = {k: v for k, v in out.items() if v is not None}      # None removes a key
    out.update(rcs_amp_real=field.real.copy(), rcs_amp_imag=field.imag.copy(),
               rcs_power=(4*np.pi*np.abs(field)**2).astype(np.float32),
               rcs_phase=np.angle(field).astype(np.float32))
    return _save_grim_npz(out, str(ctx["work"]/name))


# ---- body shadowing ----------------------------------------------------------
def sheet(n):
    g = np.linspace(-1.0, 1.0, n+1)
    return np.asarray([t for i in range(n) for j in range(n) for t in (
        ((g[i], g[j], 0), (g[i+1], g[j], 0), (g[i+1], g[j+1], 0)),
        ((g[i], g[j], 0), (g[i+1], g[j+1], 0), (g[i], g[j+1], 0)))], float)

LINES = [(-3.0, 3.0, 0.2), (-0.4, 2.6, -0.7), (-2.5, 0.3, 0.0), (-0.9, 0.9, 0.5), (1.2, 2.0, 0.1), (-3.0, 3.0, 1.5)]

@pytest.mark.parametrize("n", [1, 11, 12, 18, 40])      # 2, 242 (one leaf), 288, 648, 3200 triangles
@pytest.mark.parametrize("tilt_deg", [0.0, 20.0, -35.0])
def test_sheet_visible_fraction_is_independent_of_tessellation(n, tilt_deg):
    """Square sheet [-1,1]^2 at z=0; lines at z=-0.5. Exact answer in closed form."""
    t = np.radians(tilt_deg); shift = 0.5*np.tan(t)
    exact = [1.0 - (max(0.0, min(b, 1-shift) - max(a, -1-shift)) if abs(y) <= 1 else 0.0)/(b-a) for a, b, y in LINES]
    starts = np.array([(a, y, -0.5) for a, b, y in LINES]); ends = np.array([(b, y, -0.5) for a, b, y in LINES])
    owner, lo, hi = visible_intervals(Occluder(sheet(n)), starts, ends, np.array([np.sin(t), 0.0, np.cos(t)]))
    assert np.allclose(np.bincount(owner, weights=hi-lo, minlength=len(LINES)), exact, atol=1e-12)


def test_expansion_completes_with_default_shadowing_on_a_bor_profile_base(ctx):
    theta = np.linspace(0, np.pi, 25)
    base = write_base(ctx, "sphere.grim", body_profile_rho_m=0.15*np.sin(theta).clip(0),
                      body_profile_z_m=-0.15*np.cos(theta), body_profile_kind=np.asarray("outer_boundary"))
    run = expand([ctx["section"]], output_grim=str(ctx["work"]/"shadowed.grim"), body_grim=base, shadow=True)
    added = reopen(run["output"])[1] - ctx["ref"]
    assert np.all(np.isfinite(added))
    # a shadowed section can only lose line length; it must not gain field everywhere
    assert np.abs(added).max() <= np.abs(ctx["ref"]).max()*(1+1e-6)


# ---- base conventions --------------------------------------------------------
def test_degree_base_control(ctx):
    base = write_base(ctx, "deg.grim")
    run = expand([ctx["section"]], output_grim=str(ctx["work"]/"deg-out.grim"), body_grim=base)
    assert rel(reopen(run["output"])[1], 2*ctx["ref"]) < TOL


def test_radian_base_is_refused_or_handled(ctx):
    units = json.loads(scalar(ctx["payload"], "units")); units.update(azimuth="rad", elevation="rad")
    base = write_base(ctx, "rad.grim", azimuths=np.radians(AZ), elevations=np.radians(EL),
                      units=np.asarray(json.dumps(units)))
    try:
        run = expand([ctx["section"]], output_grim=str(ctx["work"]/"rad-out.grim"), body_grim=base)
    except ValueError:
        assert not (ctx["work"]/"rad-out.grim").exists()
        return
    assert rel(reopen(run["output"])[1], 2*ctx["ref"]) < TOL


@pytest.mark.parametrize("order", [["VV", "HH", "VH", "HV"], ["HH", "HV", "VH", "VV"], ["VV", "HV", "HH", "VH"]])
def test_four_channel_base_stays_reciprocal(ctx, order):
    lab = [str(x) for x in ctx["payload"]["polarizations"]]
    src = {c: ctx["ref"][..., lab.index("VH" if c == "HV" else c)] for c in order}
    base = write_base(ctx, "b4-"+"".join(order)+".grim", field=np.stack([src[c] for c in order], -1),
                      polarizations=np.array(order), polarization_aliases_json=np.asarray(json.dumps(order)),
                      polarization_alias_primary=np.asarray(order[0]))
    run = expand([ctx["section"]], output_grim=str(ctx["work"]/("o4-"+"".join(order)+".grim")), body_grim=base)
    payload, got = reopen(run["output"])
    out = [str(x) for x in payload["polarizations"]]
    assert out == order
    for c in order:
        assert rel(got[..., out.index(c)], 2*src[c]) < TOL, c


# ---- attitude and provenance -------------------------------------------------
def test_chained_attitude_restated_control(ctx):
    run = expand([ctx["section"]], output_grim=str(ctx["work"]/"explicit.grim"), body_grim=ctx["att_path"], **ATT)
    assert rel(reopen(run["output"])[1], 2*ctx["att"]) < TOL


def test_chained_attitude_is_inherited_or_refused(ctx):
    try:
        run = expand([ctx["section"]], output_grim=str(ctx["work"]/"implicit.grim"), body_grim=ctx["att_path"])
    except ValueError:
        return
    assert rel(reopen(run["output"])[1], 2*ctx["att"]) < TOL


def test_base_without_attitude_record_warns(ctx):
    """An imported base says nothing about attitude; assuming zero must be visible."""
    base = write_base(ctx, "plain.grim", line_expansion_provenance_json=None, requested_radar_grid_json=None)
    run = expand([ctx["section"]], output_grim=str(ctx["work"]/"plain-out.grim"), body_grim=base)
    assert any("attitude" in w.lower() for w in run["warnings"])


def test_saved_file_keeps_provenance_and_attitude(ctx):
    payload, _ = reopen(ctx["att_path"])
    record = json.loads(scalar(payload, "line_expansion_provenance_json"))
    assert record["schema"].startswith("ghost.assembly.line-expansion")
    assert json.dumps(record).count("25") and "-12" in json.dumps(record) and "40" in json.dumps(record)


# ---- cases added from Codex's review of abe8bd0 --------------------------------
def refused_or_exact(ctx, name, base, expected, **kw):
    try:
        run = expand([ctx["section"]], output_grim=str(ctx["work"]/name), body_grim=str(base), **kw)
    except ValueError:
        assert not (ctx["work"]/name).exists()
        return None
    assert rel(reopen(run["output"])[1], expected) < TOL
    return run


def test_polar_theta_base_is_refused_or_converted(ctx):
    """Degrees, but polar theta: the marker Assembly's own reader refuses (fields.py:689-697)."""
    el = [10.0, 25.0]                                   # theta 80, 65: inside [-90, 90], so it looks plausible
    run = expand([ctx["section"]], output_grim=str(ctx["work"]/"theta-ref.grim"), frequencies_ghz=FREQ,
                 azimuths_deg=AZ, elevations_deg=el)
    payload, ref = reopen(run["output"])
    units = json.loads(scalar(payload, "units"))
    units["elevation_coordinate_convention"] = "sentri_theta_top_zero"
    out = dict(payload, elevations=90.0-np.asarray(el)[::-1], units=np.asarray(json.dumps(units)),
               rcs_amp_real=ref.real[:, ::-1].copy(), rcs_amp_imag=ref.imag[:, ::-1].copy(),
               rcs_power=(4*np.pi*np.abs(ref[:, ::-1])**2).astype(np.float32),
               rcs_phase=np.angle(ref[:, ::-1]).astype(np.float32))
    base = _save_grim_npz(out, str(ctx["work"]/"theta.grim"))
    refused_or_exact(ctx, "theta-out.grim", base, 2*ref[:, ::-1])


def test_opposite_time_convention_base_is_refused_or_converted(ctx):
    base = write_base(ctx, "minus.grim", field=ctx["ref"].conj(), time_convention=np.asarray("exp(-jwt)"),
                      phase_reference=np.asarray(scalar(ctx["payload"], "phase_reference").replace("exp(+jwt)", "exp(-jwt)")))
    refused_or_exact(ctx, "minus-out.grim", base, 2*ctx["ref"].conj())


def declared_grid(**attitude):
    return np.asarray(json.dumps(dict(schema="ghost.workflow.requested-radar-grid.v1", frequencies_ghz=FREQ,
                                      azimuths_deg=AZ, elevations_deg=EL, **attitude)))


@pytest.mark.parametrize("bor_profile", [False, True])
def test_explicit_attitude_override_is_what_the_next_run_inherits(ctx, bor_profile):
    """Zero-field base declaring attitude 0; first run states ATT; second run states nothing."""
    extra = dict(requested_radar_grid_json=declared_grid(axis_az_deg=0.0, axis_el_deg=0.0, roll_deg=0.0))
    if bor_profile:      # the shared loader then supplies zeros even without a declared request
        extra = dict(body_profile_rho_m=np.array([0.0, 0.01, 0.0]), body_profile_z_m=np.array([-0.01, 0.0, 0.01]),
                     body_model_aspects_deg=np.array([0.0, 180.0]))
    tag = "bor" if bor_profile else "declared"
    base = write_base(ctx, f"zero-{tag}.grim", field=0*ctx["ref"], **extra)
    first = refused_or_exact(ctx, f"first-{tag}.grim", base, ctx["att"], shadow=False, **ATT)
    if first is not None:
        refused_or_exact(ctx, f"second-{tag}.grim", first["output"], 2*ctx["att"], shadow=False)


# ---- sweep parser ------------------------------------------------------------
def test_sweep_overflow_is_a_reported_input_error():
    from ghost_backend.ui.line_expansion import parse_samples
    assert parse_samples("0:10:2.5", "Azimuths") == (0.0, 2.5, 5.0, 7.5, 10.0)
    for text in ("0:1e308:1e-308", "0:1e12:1"):
        with pytest.raises(ValueError):
            parse_samples(text, "Azimuths")


# ==== acceptance cases added with the fix (Codex's notes on f920c8a) ==========
import threading
from unittest.mock import patch
from ghost_backend.assembly.fields import load_body_requested_radar_grid, radar_frame_basis


def test_attitude_is_stored_numerically_where_the_next_reader_looks(ctx):
    grid = load_body_requested_radar_grid(ctx["att_path"])
    assert {k: float(grid[k]) for k in ATT} == ATT
    record = json.loads(scalar(reopen(ctx["att_path"])[0], "line_expansion_provenance_json"))
    assert record["body_attitude_deg"] == ATT


def test_conflicting_attitude_on_a_nonzero_base_is_refused(ctx):
    other = dict(ATT, roll_deg=ATT["roll_deg"] + 5.0)
    with pytest.raises(ValueError, match="attitude"):
        expand([ctx["section"]], output_grim=str(ctx["work"]/"conflict.grim"), body_grim=ctx["att_path"], **other)
    assert not (ctx["work"]/"conflict.grim").exists()


def legacy_base(ctx, name, field, **changes):
    """The attitude-ATT file with optional tags absent, as an older writer would leave it."""
    payload, _ = reopen(ctx["att_path"])
    for key in ("time_convention", "polarization_basis", "line_expansion_provenance_json"):
        payload.pop(key, None)
    payload.update(changes)
    payload.update(rcs_amp_real=field.real.copy(), rcs_amp_imag=field.imag.copy(),
                   rcs_power=(4*np.pi*np.abs(field)**2).astype(np.float32),
                   rcs_phase=np.angle(field).astype(np.float32))
    return _save_grim_npz(payload, str(ctx["work"]/name))


def test_legacy_base_without_optional_tags_is_accepted_at_nonzero_attitude(ctx):
    base = legacy_base(ctx, "legacy.grim", ctx["att"])
    run = expand([ctx["section"]], output_grim=str(ctx["work"]/"legacy-out.grim"), body_grim=base)
    payload, got = reopen(run["output"])
    assert rel(got, 2*ctx["att"]) < TOL
    assert {k: float(load_body_requested_radar_grid(run["output"])[k]) for k in ATT} == ATT
    assert "exp(+jwt)" in scalar(payload, "phase_reference")


def test_contradictory_primary_phase_reference_is_refused(ctx):
    """Opposite sign declared only in phase_reference, with no optional time tag."""
    phase = scalar(reopen(ctx["att_path"])[0], "phase_reference").replace("exp(+jwt)", "exp(-jwt)")
    base = legacy_base(ctx, "phase-only.grim", ctx["att"].conj(), phase_reference=np.asarray(phase))
    with pytest.raises(ValueError, match="phase_reference"):
        expand([ctx["section"]], output_grim=str(ctx["work"]/"phase-only-out.grim"), body_grim=base)
    assert not (ctx["work"]/"phase-only-out.grim").exists()


def test_contradictory_amplitude_convention_is_refused(ctx):
    base = legacy_base(ctx, "amp.grim", ctx["att"], amplitude_convention=np.asarray("sqrt(sigma_3d)"))
    with pytest.raises(ValueError, match="amplitude_convention"):
        expand([ctx["section"]], output_grim=str(ctx["work"]/"amp-out.grim"), body_grim=base)


# ---- shadowing must actually happen --------------------------------------------
def test_shadowed_looks_lose_the_section_and_visible_looks_keep_it(ctx):
    """A short section beside a 0.15 m sphere: hidden looks add nothing, clear looks add everything."""
    R, x0, half = 0.15, 0.25, 0.02
    az = [float(a) for a in range(0, 360, 15)]; el = [0.0, 30.0]
    section = dict(ctx["section"], root=(x0, -half, 0.0), tip=(x0, half, 0.0), normal=(0.0, 0.0, 1.0))
    grid = dict(frequencies_ghz=[1.0], azimuths_deg=az, elevations_deg=el)
    free = expand([section], output_grim=str(ctx["work"]/"free.grim"), **grid)
    payload, alone = reopen(free["output"])
    theta = np.linspace(0, np.pi, 49)
    payload = dict(payload, body_profile_rho_m=(R*np.sin(theta)).clip(0), body_profile_z_m=-R*np.cos(theta),
                   body_profile_kind=np.asarray("outer_boundary"))
    payload.update(rcs_amp_real=0*alone.real, rcs_amp_imag=0*alone.real,
                   rcs_power=np.zeros(alone.shape, np.float32), rcs_phase=np.zeros(alone.shape, np.float32))
    base = _save_grim_npz(payload, str(ctx["work"]/"sphere-zero.grim"))
    out = {}
    for shadow in (True, False):
        run = expand([section], output_grim=str(ctx["work"]/f"sph-{shadow}.grim"), body_grim=base, shadow=shadow)
        out[shadow] = reopen(run["output"])[1]
    assert rel(out[False], alone) < TOL                                  # shadow off: unchanged
    # Analytic classification of each look for every point of the segment.
    directions, _ = radar_frame_basis(az, el)
    from ghost_backend.geometry.frames import to_axis_frame
    pts = to_axis_frame(np.array([(x0, y, 0.0) for y in np.linspace(-half, half, 9)]))   # looks are in the axis frame
    along = pts @ directions.T                                           # (point, look)
    miss2 = (pts**2).sum(1)[:, None] - along**2                           # squared ray-centre distance
    hidden = np.all((along < 0) & (miss2 < (0.9*R)**2), axis=0).reshape(len(az), len(el))
    clear = np.all((along > 0) | (miss2 > (1.1*R)**2), axis=0).reshape(len(az), len(el))
    assert hidden.sum() >= 4 and clear.sum() >= 4
    peak = np.abs(alone).max()
    assert np.abs(out[True][hidden]).max() < 1e-12*peak                   # nothing added behind the body
    assert np.abs(out[True][clear] - alone[clear]).max() < 1e-9*peak       # everything added in the clear
    assert np.abs(alone[hidden]).max() > 1e-3*peak                        # the hidden looks were not trivially zero


def test_occluder_method_used_by_assembly_handles_many_leaves():
    owner, lo, hi = Occluder(sheet(18)).visible_line_intervals(
        np.array([[-2.0, -1.37, -1.0]]), np.array([[2.0, 1.43, -1.0]]), np.array([0.0, 0.0, 1.0]))
    assert abs(float(np.sum(hi-lo)) - 0.5) < 1e-12


# ---- cancellation ----------------------------------------------------------------
def test_cancel_event_reaches_the_section_solver_and_stops_it(ctx):
    from ghost_backend.twod import solver
    event, seen = threading.Event(), []
    real = solver.solve_monostatic_rcs_2d_certified
    def solve(*args, **kwargs):
        seen.append(kwargs.get("abort_event") is event)
        event.set()                                # the user clicks Cancel while the solve is starting
        return real(*args, **kwargs)
    out = ctx["work"]/"cancel-solve.grim"; out.write_bytes(b"previous")
    with patch.object(solver, "solve_monostatic_rcs_2d_certified", solve), pytest.raises(InterruptedError):
        expand([ctx["section"]], output_grim=str(out), frequencies_ghz=[1.3], azimuths_deg=[0.0, 10.0],
               elevations_deg=[0.0], abort_event=event)
    assert seen == [True] and out.read_bytes() == b"previous"
    assert not list(ctx["work"].glob(".cancel-solve*"))


def test_cancel_accepted_before_publication_keeps_the_previous_file(ctx):
    from ghost_backend.io import grim
    event = threading.Event(); real = grim._save_grim_npz
    def save(payload, *args, **kwargs):
        result = real(payload, *args, **kwargs)
        if "line_expansion_provenance_json" in payload:
            event.set()                            # staged file is complete; rename not yet done
        return result
    out = ctx["work"]/"cancel-publish.grim"; out.write_bytes(b"previous")
    with patch.object(grim, "_save_grim_npz", save), pytest.raises(InterruptedError):
        expand([ctx["section"]], output_grim=str(out), frequencies_ghz=[1.0], azimuths_deg=[0.0, 10.0],
               elevations_deg=[0.0], abort_event=event)
    assert out.read_bytes() == b"previous" and not list(ctx["work"].glob(".cancel-publish*"))


# ---- combined grid size ----------------------------------------------------------
def test_oversized_combined_grid_is_refused_before_any_array_is_built(ctx):
    from ghost_backend.ui.line_expansion import parse_samples
    az = parse_samples("0:359:0.01", "Azimuths"); el = parse_samples("-90:90:0.01", "Elevations")
    def no_arrays(*args, **kwargs):
        raise AssertionError("the grid product was about to be built")
    with patch.object(np, "meshgrid", no_arrays), pytest.raises(ValueError, match="looks"):
        expand([ctx["section"]], output_grim=str(ctx["work"]/"huge.grim"), frequencies_ghz=[1.0],
               azimuths_deg=az, elevations_deg=el)
    assert not (ctx["work"]/"huge.grim").exists()
