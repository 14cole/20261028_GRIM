"""Shared 2-D monostatic choices for the GUI and local/HPC parameter blocks."""
from ghost_backend.execution.options import automatic_options, validate_options


DRIVER_CONTROL_DEFAULTS = {
    'FACTORIZATION': 'compressed',
    'MESH_STRATEGY': 'adaptive',
    'BASIS_ORDER': 1,
    'MESH_GRADING': True,
}
CONTROL_FIELDS = {
    'FACTORIZATION': 'factorization', 'MESH_STRATEGY': 'mesh_strategy',
    'BASIS_ORDER': 'basis_order', 'MESH_GRADING': 'mesh_grading',
}
FACTORIZATION_LABELS = {
    'compressed': 'Compressed (default, lower memory)',
    'dense': 'Dense (manual override)',
}
# Accepted by APIs, drivers, and saved profiles, but not offered for new GUI runs.
DIAGNOSTIC_FACTORIZATION_LABELS = {
    'hierarchical': 'Hierarchical (diagnostic)',
    'adaptive': 'Automatic backend (legacy)',
}


def run_control_options(controls=None, ram_budget_gib=None):
    """Normalize new run choices without rewriting existing saved profiles.

    Legacy ``auto`` is a spelling of the dense policy, not adaptive selection.
    Adaptive certification owns polynomial order. Its single-mesh survey uses
    the P1 reference path, so an ignored manual order must not change that run.
    """
    controls = {} if controls is None else dict(controls)
    unknown = set(controls) - set(CONTROL_FIELDS.values())
    if unknown:
        raise ValueError('Unknown run control(s): ' + ', '.join(sorted(unknown)))
    options = validate_options(dict(automatic_options(ram_budget_gib), **controls))
    if options['factorization'] == 'auto':
        options['factorization'] = 'dense'
    if options['mesh_strategy'] == 'adaptive':
        options['basis_order'] = 1
    return options


def run_control_summary(options, mesh_certification):
    """Explain the selected policy, including the uncertified survey path."""
    mode = options['factorization']
    factor = FACTORIZATION_LABELS.get(mode, DIAGNOSTIC_FACTORIZATION_LABELS.get(mode, 'Dense'))
    if mode == 'adaptive':
        factor += ' (dense or compressed)'
    mesh = options['mesh_strategy']
    if mesh == 'adaptive':
        mesh_label = ('Adaptive; polynomial order: Automatic' if mesh_certification else
                      'Adaptive selection; single P1 reference mesh (no refinement)')
    else:
        mesh_label = '{}; polynomial order: P{}'.format(mesh.capitalize(), options['basis_order'])
    return ('Factorization: {}. Mesh: {}. Corner grading: {}. {}.'.format(
        factor, mesh_label, 'On' if options['mesh_grading'] else 'Off',
        'Mesh certification: On (compare meshes)' if mesh_certification else
        'Survey \u2014 mesh convergence not checked'))
