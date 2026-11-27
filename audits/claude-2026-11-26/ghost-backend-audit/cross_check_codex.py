"""Recompute Codex's cylinder cases with my own series and compare with its stored arrays.

No solver is run. Usage: python cross_check_codex.py <extracted evidence root> [out.json]
"""
import json, sys
from pathlib import Path
import numpy as np
import reference as ref

root = Path(sys.argv[1])
B, CORE, CENTER, EPS, MU = 0.08, 0.05, (0.035, -0.021), 2.5 - 0.04j, 1.3 - 0.02j
POL = {"VV": "TE", "HH": "TM"}
rel = lambda got, want: float(np.max(np.abs(got - want)) / np.max(np.abs(want)))
out = {"reference_agreement": {}, "error_vs_my_reference": {}, "dense_vs_compressed": {}}

def mine(kind, f, angles, pol):
    kw = dict(pec={}, dielectric=dict(a=0, eps=EPS, mu=MU), coat=dict(a=CORE, eps=EPS, mu=MU))[kind]
    return ref.stored_amplitude(POL[pol], f, angles, B, center=CENTER, **kw)

z = np.load(root/"physics"/"complex_fields.npz")
for f in (2, 15):
    angles = z[f"angles_f{f}"]
    for kind in ("pec", "dielectric"):
        worst = {}
        for pol in POL:
            m = mine(kind, float(f), angles, pol)
            out["reference_agreement"][f"{kind}_{f}GHz_{pol}"] = rel(z[f"f{f}_{kind}_{pol}_reference"], m)
            for key in z.files:
                if key.startswith(f"f{f}_{kind}_") and key.endswith(f"_{pol}") and "reference" not in key:
                    panels = key.split("_")[2]
                    worst[panels] = max(worst.get(panels, 0.0), rel(z[key], m))
                    if "_dense_" in key:
                        c = z[key.replace("_dense_", "_compressed_")]
                        out["dense_vs_compressed"][key] = float(np.linalg.norm(c - z[key]) / np.linalg.norm(z[key]))
        out["error_vs_my_reference"][f"{kind}_{f}GHz"] = {k: round(100 * v, 4) for k, v in sorted(worst.items(), key=lambda kv: int(kv[0]))}
z = np.load(root/"physics"/"coating_fields.npz")
for f in (2, 15):
    angles = z[f"f{f}_angles"]; worst = {}
    for pol in POL:
        m = mine("coat", float(f), angles, pol)
        out["reference_agreement"][f"coat_{f}GHz_{pol}"] = rel(z[f"f{f}_reference_{pol}"], m)
        for key in z.files:
            if key.startswith(f"f{f}_") and key.endswith(f"_{pol}") and "reference" not in key:
                mesh = "_".join(key.split("_")[1:3])
                worst[mesh] = max(worst.get(mesh, 0.0), rel(z[key], m))
                if "_dense_" in key:
                    c = z[key.replace("_dense_", "_compressed_")]
                    out["dense_vs_compressed"][key] = float(np.linalg.norm(c - z[key]) / np.linalg.norm(z[key]))
    out["error_vs_my_reference"][f"coat_{f}GHz"] = {k: round(100 * v, 4) for k, v in worst.items()}
for label, folder in (("96_vertices", root/"certified"), ("192_vertices", root/"certified"/"finer-source")):
    z = np.load(folder/"certified_fields.npz"); angles = z["angles_deg"]
    out.setdefault("certified_error_vs_my_circle_percent", {})[label] = round(100 * max(
        rel(z[pol], mine("dielectric", 2.0, angles, pol)) for pol in POL), 4)
    out.setdefault("certified_reference_agreement", {})[label] = max(
        rel(z[f"{pol}_reference"], mine("dielectric", 2.0, angles, pol)) for pol in POL)
out["max_reference_disagreement"] = max(out["reference_agreement"].values())
out["max_dense_vs_compressed_l2"] = max(out["dense_vs_compressed"].values())
text = json.dumps(out, indent=1)
if len(sys.argv) > 2:
    Path(sys.argv[2]).write_text(text + "\n")
print(json.dumps({k: v for k, v in out.items() if k not in ("dense_vs_compressed",)}, indent=1))
