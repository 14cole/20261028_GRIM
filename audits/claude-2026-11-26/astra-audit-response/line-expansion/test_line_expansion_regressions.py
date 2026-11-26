"""Proposed regression cases for the Line Expansion fixes.

They state required behaviour, not one implementation: where a fix may either
refuse an input or handle it, both are accepted; a silent wrong field is not.
Real section solver, real files, every result reopened from disk.

    GRIM_ROOT=/path/to/checkout QT_QPA_PLATFORM=offscreen python -m pytest -q test_line_expansion_regressions.py

At ed90b65: 18 fail, 8 pass (the passing ones are controls). With trial-fix.patch: 26 pass.
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


# ---- sweep parser ------------------------------------------------------------
def test_sweep_overflow_is_a_reported_input_error():
    from ghost_backend.ui.line_expansion import parse_samples
    assert parse_samples("0:10:2.5", "Azimuths") == (0.0, 2.5, 5.0, 7.5, 10.0)
    for text in ("0:1e308:1e-308", "0:1e12:1"):
        with pytest.raises(ValueError):
            parse_samples(text, "Azimuths")
