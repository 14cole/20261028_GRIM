# Review of Claude's impedance-experiment audit

Reviewed 2026-10-29: `Claude_audit/review_of_codex_impedance_experiment.md`, saved experiment plans/factors/failure traces and current production source. This review ran no new solves and made no production changes. All 131 saved production source hashes still match. Recomputed quantities are in verification.json.

## Verdict

Agree with Claude's approval of the experiment and with retaining surface impedance as an explicit material-model override. The measured timing, material conversion, error statistics, negative control and full-size 15 GHz qualification limits are correctly represented. Existing opaque IBC input remains sufficient for the experimental override.

Agree that hierarchical memory prediction warrants investigation. However, the proposed sampling change is a promising study, not yet a demonstrated fix for the refused 2 GHz run.

## Corrections and qualifications

1. **The exact 1/50-scale storage value was not a sampling forecast.** Its saved last_plan.json says `storage_method: assembled_partner_payload`, `sampled: false`, `samples: 0`. The 351,758,448-byte allowance equals the already assembled partner operator's retained bytes. In compressed/memory.py, a geometry sample for its 4,860-DOF system otherwise takes the small_dense_ceiling branch (threshold 8,192). Therefore the 1.0x match does not validate predicting a new hierarchical operator from a handful of tiles. Reusing actual owned payload is useful, but it is different evidence.

2. **The 2-7x ratios describe storage components, not total RAM.** For the full-size 1.5 GHz case, operator forecast is 3.10 GiB versus about 0.84 GiB retained; inverse allowance is 2.60 GiB versus about 0.37 GiB retained. The full peak forecast is 7.92 GiB versus 3.93 GiB sampled private memory, including different phase lifetimes. Retained inverse bytes do not measure peak inverse construction, replacement-factor overlap or assembly workspace. The ratios identify conservatism but cannot simply discount the whole refusal.

3. **The 2 GHz fallback is a different discretization.** The published full-size 1.5 GHz system has 24,048 DOFs; the refused 2 GHz linear fallback has 85,462. It is not merely the same matrix at a slightly higher frequency. Both adaptive attempts were rejected, and the final failure lost their reasons. Whether the fallback could complete inside 12 GiB remains unmeasured. Its 33.57 GiB forecast is not a measurement of actual required RAM.

4. **Operator samples alone do not establish inverse or construction costs.** Source confirms that the forecast passes the largest material wavenumber magnitude into the geometry model and does not apply attenuation credit. Bounded sampling of actual hierarchical interactions is worth testing. It must account for both material equations/polarizations, distinguish operator storage from inverse growth, and budget the pilot, construction and live allocations. A few low-rank samples are not proof that the entire solve fits. Preserve runtime accounting and permit bounded partial progress with clear failure reasons; do not make a sample-only estimate an unconditional admission promise. The asserted sampling cost of seconds has not been measured here.

5. **The compressed failure is not a 25-second reproducer.** Its failed high-density run took 146.95 seconds; 23.39 seconds was the successful dense check, and 25.48 seconds was the lower-density compressed case. Iteration planning should use the actual failed-run cost or isolate a smaller reproducer.

## Recommendations, in implementation order

1. Preserve adaptive failure reasons and completed steps before either the conservative retry or the reference fallback. The source currently attaches these to metadata only after successful returns, so a later exception discards them. Carry structured failure evidence as well as a concise error message; preserve the original exception classification and cause. This is the clearest confirmed defect and should precede calibration of the 2 GHz refusal.
2. On compressed numerical failure, report a same-mesh dense forecast and whether a fresh dense override could fit after releasing failed solve allocations. Keep it informational: no automatic backend switch, no guarantee of convergence, and no claim that the dense option resolves a physics-model issue.
3. Develop and calibrate bounded hierarchical pilots, including inverse/construction accounting, before changing refusal policy. Use successful strongly absorbing and moderate-dielectric cases, difficult/low-loss controls, both polarizations and fresh cases held out of calibration. Revisit the 2 GHz case only with its adaptive rejection trace available. No fixed loss discount and no persistent history of prior solves is needed.
4. If a convenience UI is added, compute impedance in ohms from the selected material at each frequency and record the original material, approximation identity and impedance. Applicability information is useful; thin-section checks must be based on actual geometry, and an index/decay-length heuristic must not be labeled an accuracy certificate. Preserve direct IBC entry for intentionally specified surface models. Keep the approximation explicitly selected, not an automatic response to a large or refused bulk solve.

The experiment's original conclusion remains unchanged: worthwhile as an explicit approximation for suitable strongly absorbing materials, with full-material physics retained and full-size 15 GHz model error still unqualified. This review recommends follow-up work; it does not implement it.
