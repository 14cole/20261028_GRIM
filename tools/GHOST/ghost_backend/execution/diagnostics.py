"""Label relaxed-check audit results without changing production quality gates."""
from contextlib import contextmanager
from copy import deepcopy
from ghost_backend.execution.runtime import ScopedValue

_RELAXED = ScopedValue('ghost_diagnostic_relaxed_checks', default=None)


@contextmanager
def diagnostic_scope(relaxed_checks):
    """Suppress timing-history ingestion while an offline check is relaxed."""
    with _RELAXED.override(dict(_RELAXED.get() or {}, **(relaxed_checks or {}))):
        yield


def active():
    return bool(_RELAXED.get())


def mark_uncertified(metadata, relaxed_checks):
    """Return a labeled derivative; retain measured data and diagnostic outcomes.

    Certification/gate success is never published as production success when
    checks were relaxed. Original booleans are explicitly diagnostic evidence.
    The input metadata remains untouched, including previously hashed artifacts.
    """
    if not relaxed_checks:
        raise ValueError('Diagnostic exports must identify their relaxed checks.')
    result = deepcopy(metadata)
    def visit(value, gate=False):
        if isinstance(value, list):
            for child in value:
                visit(child, gate)
        elif isinstance(value, dict):
            if 'quality_gate' in value or 'mesh_convergence_certified' in value:
                value.update(diagnostic_only=True, uncertified=True)
            for key, child in list(value.items()):
                if key == 'mesh_convergence_certified' or (gate and key in ('passed', 'certified')):
                    value.setdefault('diagnostic_' + key, child)
                    value[key] = False
                else:
                    visit(child, gate or key in ('quality_gate', 'mesh_convergence')
                          or key.endswith('_quality_gate'))
    visit(result)
    result.update(diagnostic_only=True, uncertified=True, relaxed_checks=dict(relaxed_checks),
                  mesh_convergence_certified=False)
    result.setdefault('quality_gate', {})['passed'] = False
    return result
