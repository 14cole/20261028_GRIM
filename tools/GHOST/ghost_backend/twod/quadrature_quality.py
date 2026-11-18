"""Electrical-length qualification shared by mesh construction and certification."""
import math

CALIBRATED_PANEL_KL_MAX = 3.0


def panel_qualification(mesh, infos):
    values = []
    for element, info in zip(mesh.elements, infos):
        lengths = [float(element.length) * abs(complex(k)) for k in (info.k_plus, info.k_minus)]
        values.append(max(lengths) if all(math.isfinite(v) and v >= 0 for v in lengths) else float('nan'))
    invalid = sum(not math.isfinite(value) or value < 0 for value in values)
    exceeded = sum(math.isfinite(value) and value > CALIBRATED_PANEL_KL_MAX for value in values)
    complete = len(values) == len(mesh.elements) == len(infos) and bool(values)
    return dict(qualified=complete and not invalid and not exceeded,
        calibrated_panel_kl_max=CALIBRATED_PANEL_KL_MAX,
        maximum_panel_kl=max((v for v in values if math.isfinite(v)), default=0.),
        exceeded_panels=exceeded, invalid_panels=invalid, panel_count=len(values), complete=complete)
