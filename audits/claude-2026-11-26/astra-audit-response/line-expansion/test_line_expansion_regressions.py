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


# ==== cases added after Codex's review of d0a9b01 ==============================
def test_sections_only_output_is_usable_by_assembly_with_and_without_a_mesh(ctx):
    from ghost_backend.assembly.workflow import (
        FeatureAssemblyRequest, execute_feature_assembly, prepare_feature_assembly, prepare_feature_input_preview)
    base = ctx["work"]/"ref.grim"
    assert "requested_radar_grid_json" in ctx["payload"] and "body_profile_rho_m" not in ctx["payload"]
    mesh = ctx["work"]/"mesh.stl"
    mesh.write_text("solid p\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid p\n")
    for name, kwargs, source in (("asm-none", {}, "none"),
                                 ("asm-stl", dict(surface_mesh=mesh, surface_units="meters"), "surface_mesh")):
        assert prepare_feature_input_preview(base_grim=base, **kwargs).body_source == source
        plan = prepare_feature_assembly(FeatureAssemblyRequest(base_grim=base, output_grim=ctx["work"]/f"{name}.grim", **kwargs))
        done = execute_feature_assembly(plan, acknowledged_plan_sha256=plan.prepared_plan_sha256)
        assert rel(reopen(done)[1], ctx["ref"]) == 0.0


def rotated_body_without_request(ctx, name):
    """A non-zero field at attitude ATT whose file carries a BoR profile but no attitude record."""
    payload, _ = reopen(ctx["att_path"])
    for key in ("requested_radar_grid_json", "line_expansion_provenance_json"):
        payload.pop(key, None)
    payload.update(body_profile_rho_m=np.array([0.0, 0.01, 0.0]), body_profile_z_m=np.array([-0.01, 0.0, 0.01]),
                   body_model_aspects_deg=np.array([0.0, 180.0]))
    return _save_grim_npz(payload, str(ctx["work"]/name))


def test_unknown_attitude_is_reported_as_an_assumption_and_can_be_stated(ctx):
    base = rotated_body_without_request(ctx, "rotated-no-request.grim")
    assert float(load_body_requested_radar_grid(base)["axis_az_deg"]) == 0.0      # the reader's fallback zeros
    implicit = expand([ctx["section"]], output_grim=str(ctx["work"]/"unk-implicit.grim"), body_grim=base, shadow=False)
    assert any("assum" in w.lower() for w in implicit["warnings"])
    record = json.loads(scalar(reopen(implicit["output"])[0], "line_expansion_provenance_json"))
    assert set(record["body_attitude_source"].values()) == {"assumed"}
    stated = expand([ctx["section"]], output_grim=str(ctx["work"]/"unk-stated.grim"), body_grim=base, shadow=False, **ATT)
    assert rel(reopen(stated["output"])[1], 2*ctx["att"]) < TOL and not stated["warnings"]
    assert json.loads(scalar(reopen(stated["output"])[0], "line_expansion_provenance_json"))["body_attitude_source"] == dict.fromkeys(ATT, "stated")
    # the assumption stays visible when the assumed file is expanded again
    again = expand([ctx["section"]], output_grim=str(ctx["work"]/"unk-again.grim"), body_grim=implicit["output"], shadow=False)
    assert any("assum" in w.lower() for w in again["warnings"])


def test_partly_stated_attitude_uses_the_stated_angle_and_flags_the_rest(ctx):
    base = rotated_body_without_request(ctx, "rotated-no-request-2.grim")
    run = expand([ctx["section"]], output_grim=str(ctx["work"]/"unk-partial.grim"), body_grim=base, shadow=False,
                 axis_az_deg=ATT["axis_az_deg"])
    record = json.loads(scalar(reopen(run["output"])[0], "line_expansion_provenance_json"))
    assert record["body_attitude_source"] == dict(axis_az_deg="stated", axis_el_deg="assumed", roll_deg="assumed")
    assert any("axis_el_deg" in w and "axis_az_deg" not in w for w in run["warnings"])


def test_physically_equivalent_attitude_is_not_a_conflict(ctx):
    same = dict(axis_az_deg=ATT["axis_az_deg"] + 360.0, axis_el_deg=ATT["axis_el_deg"], roll_deg=ATT["roll_deg"] - 360.0)
    run = expand([ctx["section"]], output_grim=str(ctx["work"]/"equiv.grim"), body_grim=ctx["att_path"], **same)
    assert rel(reopen(run["output"])[1], 2*ctx["att"]) < TOL
    assert {k: float(load_body_requested_radar_grid(run["output"])[k]) for k in ATT} == ATT


def test_power_and_phase_base_gives_an_output_that_expands_again(ctx):
    """Version-1 layout without the optional complex-field-domain tag."""
    from ghost_backend.assembly.fields import RADAR_COMPONENT_FIELD_DOMAIN
    payload, _ = reopen(ctx["att_path"])
    for key in ("complex_field_domain", "rcs_amp_real", "rcs_amp_imag", "raw_complex_amplitude_preserved",
                "line_expansion_provenance_json"):
        payload.pop(key, None)
    payload["rcs_power"] = 4*np.pi*np.abs(ctx["att"])**2; payload["rcs_phase"] = np.angle(ctx["att"])
    base = _save_grim_npz(payload, str(ctx["work"]/"power-phase.grim"), format_version=1)
    with np.load(base) as stored:
        assert "complex_field_domain" not in stored.files and "rcs_complex" not in stored.files
    first = expand([ctx["section"]], output_grim=str(ctx["work"]/"pp-1.grim"), body_grim=base)
    out, field = reopen(first["output"])
    assert rel(field, 2*ctx["att"]) < TOL and scalar(out, "complex_field_domain") == RADAR_COMPONENT_FIELD_DOMAIN
    assert "metadata_advisories_json" in out and str(ctx["work"]) not in scalar(out, "metadata_advisories_json")
    second = expand([ctx["section"]], output_grim=str(ctx["work"]/"pp-2.grim"), body_grim=first["output"])
    assert rel(reopen(second["output"])[1], 3*ctx["att"]) < TOL


def test_oversized_base_is_refused_after_reading_only_its_axes(ctx):
    with np.load(ctx["att_path"]) as handle:
        cls = type(handle)
    read, real = [], cls.__getitem__
    def record(self, member):
        read.append(member); return real(self, member)
    out = ctx["work"]/"big-base-out.grim"; out.write_bytes(b"previous")
    with patch.object(cls, "__getitem__", record), patch.object(wing, "MAX_LOOKS", len(AZ)*len(EL)-1), \
            pytest.raises(ValueError, match="too large"):
        expand([ctx["section"]], output_grim=str(out), body_grim=ctx["att_path"])
    assert sorted(read) == ["azimuths", "elevations", "frequencies", "polarizations"]
    assert out.read_bytes() == b"previous"


def test_output_size_counts_every_channel_of_the_base(ctx):
    order = ["VV", "HH", "VH", "HV"]
    lab = [str(x) for x in ctx["payload"]["polarizations"]]
    field = np.stack([ctx["ref"][..., lab.index("VH" if c == "HV" else c)] for c in order], -1)
    base = write_base(ctx, "four-for-size.grim", field=field, polarizations=np.array(order),
                      polarization_aliases_json=np.asarray(json.dumps(order)), polarization_alias_primary=np.asarray("VV"))
    three_channel_count = field[..., :3].size
    with patch.object(wing, "MAX_OUTPUT_SAMPLES", three_channel_count), pytest.raises(ValueError, match="4 channels"):
        expand([ctx["section"]], output_grim=str(ctx["work"]/"four-size-out.grim"), body_grim=base)


def test_axis_limit_holds_at_the_boundary_for_parser_and_api(ctx):
    from ghost_backend.ui.line_expansion import parse_samples
    assert len(parse_samples("0:99999:1", "Azimuths")) == wing.MAX_AXIS_SAMPLES
    for text in ("0:100000:1", "0:99999.9999999995:1"):
        try:
            assert len(parse_samples(text, "Azimuths")) <= wing.MAX_AXIS_SAMPLES
        except ValueError:
            pass
    with patch.object(np, "meshgrid", side_effect=AssertionError("built")), pytest.raises(ValueError, match="frequencies"):
        expand([ctx["section"]], output_grim=str(ctx["work"]/"manyf.grim"), frequencies_ghz=range(1, 100_002),
               azimuths_deg=[0.0], elevations_deg=[0.0])


@pytest.mark.parametrize("where", ["solver_settings_event", "top_level_event"])
@pytest.mark.parametrize("with_callback", [False, True])
def test_a_cancel_from_any_source_is_honoured(ctx, where, with_callback):
    """Event set before the run, optionally beside a callback that says 'not canceled'."""
    event = threading.Event(); event.set()
    kw = dict(section_solver_kwargs={"abort_event": event}) if where == "solver_settings_event" else dict(abort_event=event)
    if with_callback:
        kw["cancel_check"] = lambda: False
    out = ctx["work"]/f"src-{where}-{with_callback}.grim"; out.write_bytes(b"previous")
    with pytest.raises(InterruptedError):
        expand([ctx["section"]], output_grim=str(out), frequencies_ghz=[1.0], azimuths_deg=[0.0], elevations_deg=[0.0], **kw)
    assert out.read_bytes() == b"previous"


def test_event_set_at_publication_is_honoured_beside_a_false_callback(ctx):
    from ghost_backend.io import grim
    event = threading.Event(); real = grim._save_grim_npz
    def save(payload, *args, **kwargs):
        result = real(payload, *args, **kwargs)
        if "line_expansion_provenance_json" in payload:
            event.set()
        return result
    out = ctx["work"]/"pub-callback.grim"; out.write_bytes(b"previous")
    with patch.object(grim, "_save_grim_npz", save), pytest.raises(InterruptedError):
        expand([ctx["section"]], output_grim=str(out), frequencies_ghz=[1.0], azimuths_deg=[0.0], elevations_deg=[0.0],
               abort_event=event, cancel_check=lambda: False)
    assert out.read_bytes() == b"previous"


def test_two_jobs_for_one_destination_publish_only_the_uncanceled_one(ctx):
    """A (30 deg) and B (60 deg) both stage; B is canceled; A publishes first, then B unwinds."""
    from ghost_backend.io import grim
    real = grim._save_grim_npz
    staged = {n: threading.Event() for n in "AB"}; release = {n: threading.Event() for n in "AB"}
    cancel = {n: threading.Event() for n in "AB"}; paths, results = {}, {}
    def save(payload, path, *args, **kwargs):
        result = real(payload, path, *args, **kwargs)
        name = threading.current_thread().name
        if name in staged and "line_expansion_provenance_json" in payload:
            paths[name] = str(path); staged[name].set(); assert release[name].wait(60)
        return result
    out = ctx["work"]/"shared.grim"
    def work(name, az):
        try:
            expand([ctx["section"]], output_grim=str(out), frequencies_ghz=[1.0], azimuths_deg=[az], elevations_deg=[0.0],
                   abort_event=cancel[name]); results[name] = "saved"
        except InterruptedError:
            results[name] = "canceled"
    a = threading.Thread(target=work, args=("A", 30.0), name="A"); b = threading.Thread(target=work, args=("B", 60.0), name="B")
    with patch.object(grim, "_save_grim_npz", save):
        try:
            a.start(); assert staged["A"].wait(60)
            b.start(); assert staged["B"].wait(60)
            cancel["B"].set()
            release["A"].set(); a.join(60); release["B"].set(); b.join(60)
        finally:
            release["A"].set(); release["B"].set()
    assert results == {"A": "saved", "B": "canceled"} and paths["A"] != paths["B"]
    assert np.asarray(reopen(out)[0]["azimuths"]).tolist() == [30.0]
    assert not list(ctx["work"].glob(".shared.grim.tmp.*"))


def test_publication_gate_tells_a_late_cancel_it_was_too_late(ctx):
    gate, event = wing.PublicationGate(), threading.Event()
    seen = {}
    real = os.replace
    def at_rename(src, dst, *a, **k):
        if str(dst) == str(out):                                # the final rename, not the staging write
            seen["accepted"] = gate.request_cancel(event)      # the click lands after the last check
        return real(src, dst, *a, **k)
    out = ctx["work"]/"gate.grim"; out.write_bytes(b"previous")
    with patch.object(os, "replace", at_rename):
        expand([ctx["section"]], output_grim=str(out), frequencies_ghz=[1.0], azimuths_deg=[0.0], elevations_deg=[0.0],
               abort_event=event, publication_gate=gate)
    assert seen == {"accepted": False} and not event.is_set() and out.read_bytes() != b"previous"
    early = wing.PublicationGate(); event2 = threading.Event()
    assert early.request_cancel(event2) and event2.is_set()
