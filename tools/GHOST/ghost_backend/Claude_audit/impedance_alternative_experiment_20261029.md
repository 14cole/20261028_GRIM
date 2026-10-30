# Handoff: optional surface-impedance experiment

## Decision for review

The evidence supports retaining the existing opaque IBC input as an explicit experimental material approximation for this strongly absorbing magnetic material. It does not support automatic replacement of bulk material or a generic approximation for every dielectric. No production code, default solver policy, or UI was changed. A configured experimental geometry is supplied in the audit folder, so no additional backend mode is required.

Your earlier estimate of roughly one minute for the full-size 15 GHz impedance case was borne out: 67.816 s, repeated at 67.725 s. The published mesh contains 10,143 scalar nodes, with 1.936 GiB sampled process-tree RSS and 2.730 GiB private bytes. Mesh certification validates the selected model; full-size 15 GHz bulk-model accuracy remains unqualified.

## Evidence

See `Codex_audit/impedance_alternative_20261029/README.md`, METHOD.md, summary.json, analytic.json, evidence_validation.json, source_hashes.json, plans and runs. All raw failed trials are retained. The standalone comparison figure is available as PNG and PDF.

There were 19 serial numerical trials: 16 certified successes and 3 retained failures/refusals. All primary matched timings use compressed factorization with automatic CPU allocation and the same 12 GiB study reservation. A single explicit dense run supplies an independent numerical cross-check after a compressed refinement failure. No regression suite ran alongside timing measurements; no production changes require a new regression claim.

- Full 12 ft x 3 ft dogleg, 1.5 GHz: bulk 86.167 s versus impedance 3.271 s (26.3x); peak private memory 3.926 versus 0.699 GiB. Relative complex-field L2 error: VV 0.191%, HH 0.586%. Maximum RCS error above the -30 dB bulk level: VV 0.036 dB, HH 0.369 dB.
- Three scaled versions at 15 GHz: 26.8-51.2x faster in primary pairs. Relative complex-field L2 errors span 0.191-1.224%. The 1/10-size 15 GHz and full-size 1.5 GHz cases are electrically equivalent for this nondispersive synthetic material, not independent physics qualifications.
- Full-size 15 GHz: bulk fails the 100,000-panel limit during geometry preparation; impedance passes in about 68 seconds. No measured full-size bulk-versus-IBC error is available at 15 GHz.
- The full-size IBC density check changes VV/HH by only 0.000942% / 0.000245% of peak. Adaptive refinement produces 3,381 versus 3,593 panels, not a strict doubling of the final mesh. The repeat fields are identical.
- Independent cylinder series: at 15 GHz, worst absolute RCS difference 0.005685 dB over both polarizations and radii 5-457.2 mm. Truncation and reference-formula assertions pass. A weakly absorbing moderate dielectric negative control exceeds 12 dB error in one case.

## Explicit input and interpretation

The synthetic bulk material is eps_r = 101.19 - 11.88j, mu_r = 3.45 - 3.47j. The surface value is **77.95162063057441 - 27.198691307695334j ohms**. Do not enter the normalized 0.20691624 - 0.07219672j value into an ohms field. The experimental conversion uses TYPE 2 opaque IBC, not TYPE 1 sheet or a TYPE 3 segment with an added IBC flag. Geometry and original source request remain intact.

`Codex_audit/impedance_alternative_20261029/experimental_full_size_impedance_geometry.json` contains the explicit optional input. Per-run request.json records the entire request and options. This is one sharp dogleg contour and one representative high-contrast material; it is not validation of arbitrary inlets, coatings, thin structures, measured material dispersion or full 3D geometry.

Complex-field errors use all 360 unique angles, with no phase fitting. dB statistics exclude bulk RCS below -30 dB relative to its peak; the included angle counts are printed. Unfiltered errors can be larger, reaching 3.23 dB in a weak VV response in the 1/10-size case. One-degree sampling does not certify unsampled angular structure. No five-minute timing saving was measured in a completed matched pair; capacity and multiplicative savings are the demonstrated benefit.

## Concrete solver follow-ups exposed by the experiment

1. `runs/s50_bulk_refined`: compressed GMRES fails its convergence cap after 146.947 s. The same geometry and density under explicit dense factorization certifies in 23.390 s; it agrees with the original compressed lower-density bulk result within 0.000046% of peak. This is a useful bounded reproducer for compressed robustness and diagnostic quality. Do not weaken convergence thresholds or automatically switch physics to make it pass.
2. `runs/full2_bulk`: after the adaptive attempt, a linear fallback forecast requests 33.57 GiB for 85,462 DOFs and is refused against the 12 GiB study reservation after 56.645 s. Peak observed private memory before refusal is 3.418 GiB. The impedance counterpart certifies in 3.679 s. This is a forecast refusal, not measured use of 33.57 GiB; investigate the preceding adaptive rejection and fallback forecast separately before making memory claims.
3. A more prominent UI affordance, if desired, should select a **material approximation**, preserve the full-material definition, record the resulting physical impedance and frequency dependence, and explicitly label outputs. It should not add a dense/compressed backend-picker rule.

## Integrity and reproduction

Revision: 743d6391dfa18a7b71c369e4553d5d7b39194155. Windows, Python 3.11, 8 physical / 16 logical cores, 31.103 GiB reported physical RAM, Balanced power profile. 131 production Python source hashes and all 85 historical evidence hashes were verified unchanged. Study watchdog bounds are documented in METHOD.md and are not proposed production RAM reserves. No watchdog terminated a trial.

Run the four plans serially in a fresh dated audit directory; existing run folders intentionally cause refusal rather than overwrite. The analytic and analysis scripts rebuild summaries. Review the report's separation of numerical convergence, material approximation error and resource feasibility before promoting any broader claims.
