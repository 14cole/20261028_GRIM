"""How large is the stadium K far-field error in terms that matter to a solve?  Uses the saved full matrices."""
import json, numpy as np
out = {}
for case in ('matrix-stadium-1536', 'matrix-stadium-sep3', 'matrix-square-1400'):
    z = {kd: {key: np.load('results/%s-%s.npz' % (case, kd))[key] for key in ('reference_rows', 'actual_matrix')} for kd in ('S', 'K')}
    S, K = z['S']['reference_rows'], z['K']['reference_rows']; k = 40-.8j if 'stadium' in case else 40.
    eS = z['S']['actual_matrix']-S; eK = z['K']['actual_matrix']-K; r, c = np.unravel_index(np.argmax(abs(eK)), eK.shape)
    T = K+1j*k*S; eT = eK+1j*k*eS
    out[case] = dict(K_max_entry=float(abs(K).max()), kS_max_entry=float(abs(k*S).max()), K_abs_error_max=float(abs(eK).max()), kS_abs_error_max=float(abs(k*eS).max()),
        K_error_over_K_max=float(abs(eK).max()/abs(K).max()), K_error_over_kS_max=float(abs(eK).max()/abs(k*S).max()),
        combined_block_error_max_over_max=float(abs(eT).max()/abs(T).max()), combined_block_error_fro=float(np.linalg.norm(eT)/np.linalg.norm(T)),
        K_error_fro_over_K_fro=float(np.linalg.norm(eK)/np.linalg.norm(K)), K_fro=float(np.linalg.norm(K)), kS_fro=float(np.linalg.norm(k*S)),
        worst_entry_reference=float(abs(K[r, c])), fraction_of_K_entries_exactly_zero=float(np.mean(K == 0)),
        K_error_p50_p99_abs=[float(np.percentile(abs(eK), q)) for q in (50, 99, 100)])
print(json.dumps(out, indent=1))
