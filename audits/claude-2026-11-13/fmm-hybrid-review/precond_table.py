import json
for l in open('precond.jsonl'):
    r=json.loads(l)
    if 'error' in r: print('FAILED', r); continue
    print('\n## n=%d k=%s %s eps=%s unknowns=%d dense=%.0f MiB cap=%d'%(r['n'],r['k'],r['kind'],r.get('eps',[3,-.08]),r['unknowns'],r['dense_mib'],r['max_iterations']))
    for x in r['results']:
        if 'error' in x: print('  %-48s ERROR %s'%(x['preconditioner'],x['error'][:60])); continue
        print('  %-48s its %-10s conv %-5s res %.1e  factor %7.1f MiB (%.2f dense) setup %.1fs solve %.1fs %s'%(x['preconditioner'],'/'.join(map(str,x['iterations'])),all(x['converged']),x['true_residual'],x['factor_mib'],x['factor_over_dense'],x['setup_s'],x['solve_s'],('err %.0e rank %d'%(x['approximation_error'],x['max_block_rank'])) if 'approximation_error' in x else ''))
