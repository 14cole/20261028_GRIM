"""Dimensionless compression only; stored coefficients retain physical units.

Under x -> s*x and k -> k/s the Galerkin S, K/D and W operators scale
as s**2, s and 1. Positive diagonal multipliers remove these units before
rank selection. They never rescale the public operator, RHS or solution.
"""
import numpy as np


def compression_scales(oracle):
    n = oracle.n
    rows, columns = np.ones(n), np.ones(n)
    kind = getattr(oracle, 'kind', None)
    layout = getattr(oracle, 'layout', None)
    if kind in ('dielectric', 'robin', 'sheet', 'thin'):
        k = abs(complex(oracle.k0))
    elif layout is not None:
        incident = [p['k'] for p in layout['region_props'].values() if p['has_incident']]
        k = abs(complex(incident[0])) if incident else 0.
    else:
        return rows, columns, 'identity'
    if not np.isfinite(k) or k <= 0 or not np.isfinite(k*k) or k*k == 0:
        raise ValueError('Compression requires a finite positive reference wavenumber.')
    if kind == 'dielectric':
        rows[:oracle.nn] = k
        columns[oracle.nn:] = k
    elif kind == 'robin':
        rows[:] = np.where(oracle.pec_nodes, k*k, k)
    elif kind == 'sheet':
        rows[:] = k*k if oracle.pol == 'TM' else 1.
        rows[getattr(oracle, 'endpoints', [])] = 1.
    elif kind == 'thin' and oracle.B == 0:
        rows[:] = k
    elif layout is not None:
        from ghost_backend.twod.constants import EPS
        for mi, interface in enumerate(layout['ifaces']):
            rm, rp = interface['r_m'], interface['r_p']
            if rm < 0 or rp < 0:
                start, count = layout['dof_map'][mi, 'plus' if rm < 0 else 'minus']
                pec = (np.abs(interface['robin_alpha']) <= EPS if layout['polarization'] == 'TM'
                       else np.zeros(count, bool))
                rows[start:start+count] = np.where(pec, k*k, k)
            else:
                flux, count = layout['dof_map'][mi, 'minus']
                trace, _ = layout['dof_map'][mi, 'plus']
                rows[flux:flux+count] = k
                rows[trace:trace+count] = k*k
    else:
        return rows, columns, 'identity'
    return rows, columns, 'galerkin_physical_units_v1'
