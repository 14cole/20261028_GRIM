"""Small, serializable failure evidence; diagnostics never choose a backend."""
import copy
import json
import math

NOTE_PREFIX = 'Solver diagnostics: '


def attach(exc, key, value):
    """Preserve exception type/cause and include evidence in existing traceback logs."""
    details = dict(getattr(exc, 'solver_diagnostics', {}))
    details[key] = copy.deepcopy(value)
    note = NOTE_PREFIX + json.dumps(details, allow_nan=False, default=str)
    exc.solver_diagnostics = details
    notes = [n for n in getattr(exc, '__notes__', []) if not n.startswith(NOTE_PREFIX)]
    exc.__notes__ = notes
    if hasattr(exc, 'add_note'):
        exc.add_note(note)


def adaptive_failure(exc, coarsening, reason, steps, transition):
    compact = [{k: v for k, v in step.items() if k in (
        'polynomial_degree', 'panels', 'nodes', 'seconds', 'backend', 'coarsening',
        'angle_batch_size', 'status', 'error_type', 'reason')} for step in steps]
    record = dict(initial_coarsening=coarsening, reason=reason,
                  transition=transition, steps=compact)
    previous = getattr(exc, 'solver_diagnostics', {}).get('adaptive_failures', [])
    attach(exc, 'adaptive_failures', [record] + previous)
    if transition != 'numerical_failure':
        # Keep full reasons/steps in the structured record, but avoid repeating
        # every earlier dense advisory in the user-facing exception string.
        brief = reason.split(' Dense override', 1)[0]
        brief = brief.split(' Review the saved RAM budget', 1)[0]
        brief = brief if len(brief) <= 500 else brief[:460] + ' [see full diagnostic record]'
        exc.args = (str(exc) + ' Earlier adaptive attempt (coarsening {:g}): {}.'.format(
            coarsening, brief.rstrip('.')),) + exc.args[1:]


def dense_advisory(state):
    """Forecast a fresh, explicitly selected dense solve of this exact mesh only."""
    from ghost_backend.execution.options import current_options, execution_scope, from_environment
    from ghost_backend.execution import memory_budget
    from ghost_backend.execution.angle_batch import scope as fresh_batch_scope
    from ghost_backend.compressed.worker_pool import retained_bytes
    from ghost_backend.twod import solver
    resources = dict(state.current_resources)
    if not resources.get('system_dofs'):
        return dict(status='unavailable', reason='No failed-mesh resource record is available.')
    workers = retained_bytes()
    options = dict(current_options() or from_environment(), factorization='dense')
    # A new retry does not inherit a failed attempt's temporary batch shrink.
    with execution_scope(options), fresh_batch_scope():
        peak = solver._estimate_memory_gb(resources['nodes'], False,
            n_regions=resources.get('n_regions', 1), system_dofs=resources['system_dofs'],
            operator_matrices=resources.get('operator_matrices'), dense_resources=resources,
            n_rhs=state.n_rhs, solver_method=solver.EXPERIMENTAL_METHOD)
        # The ordinary dense forecast includes the current tile team. A fresh
        # explicit retry releases that failed solve's workers and factors first.
        peak = max(0., peak-workers/memory_budget.GIB)
        ledger = memory_budget.current()
        limit = ledger.limit() if ledger is not None else solver._solve_memory_limit_gb()
    if not all(math.isfinite(v) and v >= 0 for v in (peak, limit)):
        raise ValueError('Dense forecast or available allowance is not finite and nonnegative.')
    fits = peak <= limit
    action = ('Select Dense explicitly to retry.' if fits else
              'A dense retry is not currently estimated to fit.')
    return dict(status='estimated', peak_gib=peak, available_limit_gib=limit,
        fits=fits, system_dofs=resources['system_dofs'], nodes=resources['nodes'],
        angle_batch_size=options.get('angle_batch_size', 256),
        basis_width=resources.get('basis_width'), formulation=resources.get('formulation'),
        scope='failed_mesh_only_after_releasing_failed_solve', automatic_retry=False,
        message=('Dense override for this mesh at angle batch size {} is estimated at {:.2f} GiB; {} the '
                 'currently estimated {:.2f} GiB allowance after releasing the failed solve. '
                 '{} Memory must be checked again; '
                 'later mesh refinement and convergence are not guaranteed.').format(
                     options.get('angle_batch_size', 256), peak,
                     'fits' if fits else 'does not fit', limit, action))


def invoke(function, args, kwargs):
    """Annotate numerical failures while the exact mesh/options are still active."""
    from ghost_backend.execution.errors import BackendNumericalError
    from numpy.linalg import LinAlgError
    try:
        return function(*args, **kwargs)
    except (BackendNumericalError, LinAlgError) as exc:
        from ghost_backend.compressed.runtime import enabled
        from ghost_backend.execution.cpu import current_state
        state = current_state()
        if enabled() and state is not None and 'dense_override' not in getattr(exc, 'solver_diagnostics', {}):
            try:
                advisory = dense_advisory(state)
            except Exception as diagnostic_error:
                # An optional estimate must never replace the numerical error.
                advisory = dict(status='unavailable', reason=str(diagnostic_error))
            attach(exc, 'dense_override', advisory)
            if advisory.get('message'):
                exc.args = (str(exc) + ' ' + advisory['message'],) + exc.args[1:]
        raise
