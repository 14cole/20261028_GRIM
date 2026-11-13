# Solver numerical follow-ups: Claude review and implementation

Branch: `codex/solver-numerical-followups-2026-11-12`.
Production base: `965d9417156d3f61b593310e27d17af2ea0cd19a`.
Reviewed Claude evidence: `audits/claude-2026-11-12/solver-workflow-improvements-review/`, pinned at `095df528656718130e712918c0281d07edaf4cd8`.

## Conclusions and scope

Claude's correctness conclusions are supported. All 63 evidence blobs were checked against the pinned Git tree, and the complete field arrays reproduce the reported scale and ordinary-model differences (`CLAUDE_RECOMPUTED.json`). The proposed condition-probe explanation was investigated rather than assumed.

| Finding | Disposition |
|---|---|
| F1: single-dielectric compressed overhead | Correct duplicate condition-stage timing; test probe stopping and inverse initialization separately. Retain strict probes; initialize large single-dielectric hierarchical inverses more accurately to avoid rebuilding them. |
| F2: Dense extreme-scale weakness | Equilibrate the actual LU buffer using existing condition scales; transform normal, transpose and adjoint inverse actions. Refine and gate in both physical and equilibrated coordinates. |
| F3: legacy tile scaling | Normalize tile compression, unscale stored factors, verify physical and normalized full-tile errors, and extend both refinement and original-coefficient error bounds. Include nonlocal thin layers, process workers and partner spooling. |
| F4: test dependency | State `threadpoolctl` explicitly in the reproduction requirements. No new production dependency. |

No GUI controls, native binaries, mesh certification thresholds, condition-number limits, precision defaults or backend choices were added or removed. Dense field results can change because factorization and correction are now better scaled. Existing disk storage still retains the LU in RAM; this is not out-of-core LU.

## F1: establish the cause before optimizing

### The condition-stage percentage was inflated

`HMatrixFactor._condition` and its superclass both had a `condition_estimation` timer. For the ordinary path one polarization generated two stage calls and roughly twice its actual elapsed condition time. The total solve wall time was unaffected. Thus Claude's 17.6 seconds / roughly 40% figure cannot be read as a disjoint wall-time share; it includes duplicate timing and, when triggered there, a factor rebuild. The new code times the ordinary or block-balanced path once each. Nested stages such as factorization remain inclusive.

Instrumentation also confirmed a real cost: the first condition probes could cause the `1e-8` inverse to be rebuilt at `1e-10`. Merely stopping probes sooner moved that rebuild to the field solve and did not reliably save time.

| 8,000-unknown dielectric, 181 angles | Before (s) | After (s) | Time reduction |
|---|---:|---:|---:|
| Pair 1 | 70.34 | 53.20 | 24.4% |
| Pair 2 | 62.63 | 56.68 | 9.5% |
| Pair 3 | 82.18 | 71.41 | 13.1% |
| Median | 70.34 | 56.68 | 19.4% |

All six full field arrays are bitwise identical across each matched pair. Both policies report condition estimate 3598.7517892362216. Condition-stage call count changes from four to two for two polarizations. These are three observations on a shared host, not a statistical performance guarantee. The first baseline overlapped approximately 0.8 seconds of focused tests at startup; it is retained, and all pairs are disclosed.

| Peak process RSS (GiB) | Before | After |
|---|---:|---:|
| Pair 1 | 1.316 | 1.153 |
| Pair 2 | 1.256 | 1.260 |
| Pair 3 | 1.260 | 1.247 |

Separate two-repeat mechanism experiments (before the final strict-policy table):

| Initial inverse / probes | Run 1 (s) | Run 2 (s) |
|---|---:|---:|
| Original coarse inverse / strict probes | 56.68 | 55.92 |
| Coarse inverse / relaxed probes | 56.52 | 58.63 |
| Tight inverse / relaxed probes | 48.76 | 49.96 |

The relaxed-probe experiment is **not production code**. Production retains the 3e-15 refinement target, the physical and scaled criteria, original-coefficient acceptance bounds, exact sample-row checks and condition threshold. The selected optimization starts single-dielectric hierarchical systems of at least 4,096 unknowns at `1e-10`. This is a calibrated performance heuristic, not a maximum size or an accuracy gate. Other formulations retain the prior initial policy. The existing compact `1e-6` retry remains available if the stronger inverse does not fit.

| Independent holdout | Before (s) | After (s) | Change in elapsed time |
|---|---:|---:|---:|
| 6,000-unknown dielectric | 40.19 | 32.42 | -19.3% |
| 12,000-unknown dielectric | 90.68 | 75.39 | -16.9% |
| 3 GHz airfoil | 48.77 | 51.07 | +4.7% |
| Lossless irregular dielectric star | 24.89 | 24.61 | -1.1% |
| Nonlocal thin layer, TE 2,430 / TM 1,215 unknowns | 154.94 | 103.67 | -33.1% |

These are single matched pairs. Airfoil was slower in this run despite bitwise-identical fields and unchanged initialization policy. The lossless star was essentially unchanged in time; its inverse storage increased about 14% (TE 82.21 to 94.17 MB, TM 82.45 to 94.20 MB), while requiring fewer corrections. The stronger initialization is therefore not a universal speed or RAM improvement. The existing compact retry is covered by a forced-allocation-failure control.

The original `probe-before` diagnostic overlapped two small Dense correctness controls, so it is excluded from timing comparisons. Fresh-process timing tables use subsequent sequential runs. The audit-only probe wrappers use a process-local global override and must not be used for concurrent requests; production uses neither override.

## F2: Dense LU and refinement

Let `Aeq = diag(1/r) A diag(1/c)`, with the same positive row and column scales already used by the condition estimate. LU is now applied to `Aeq` in the existing owned factor buffer. For a normal solve, factor RHS is `b/r` and physical solution is `y/c`. Transpose and adjoint actions exchange `r` and `c`; the scales are real. The condition estimator still estimates the same equilibrated matrix, using these transformed physical inverse actions.

The original coefficients remain unchanged in the in-memory residual matrix or on disk. The disk path writes the original before scaling its buffer, evaluates every original row for residuals, and restores the original buffer before paired-polarization reuse. No additional full matrix is allocated. The scale vectors are reused, and LU-buffer scaling is done in bounded column blocks with cancellation checkpoints.

Refinement retains the physical infinity-norm check and adds the equilibrated 1-norm check, reusing the already computed equilibrated norm. It targets 3e-15 in the scaled system, allows at most five improving corrections, and requires **both** final backward errors to meet the unchanged 1e-12 limit. This does not lower the condition gate or create a mesh certificate.

At radii 0.01 and 100, with frequency inversely scaled, the matched 2,000-input-panel coated-circle Dense field drift falls from **2.90167e-8 to 2.62759e-11**, roughly a thousand-fold reduction. This local discretization differs from Claude's 2,040-input-panel scan, so those values must not be treated as the same test. New small/large cases differ from the old large reference by 2.28883e-11 and 2.86142e-11 respectively. Dielectric Dense cross-scale drift is 1.08065e-13.

For the coated small-scale case, disk and in-memory Dense emit **bitwise-identical full fields**. Focused tests separately verify normal, transpose and conjugate-transpose inverse actions on known solutions, actual disk-factor restoration, zero RHS and an ill-conditioned refusal. The intermediate stopping-only experiment (`dense-coat-*`, 1.37189e-11 drift) predates actual equilibrated LU and is retained as a separate experiment.

Higher-order compressed/Dense differences are 4.55554e-11 for P2 coated and 3.95115e-12 for P3 dielectric. The final hierarchical coated-circle fields differ from final Dense by up to 8.21286e-10; improved Dense scaling does not make the two factorizations bitwise equivalent.

## F3: legacy tiles, including nonlocal thin layers

`StreamedOperator` obtains the same dimensional row/column multipliers as the hierarchy. Compression acts on `R A C`, then unscales the factors. Both the physical and normalized **complete tile** differences are checked after unscaling, including the factor-storage reconstruction rounding. A failed compression retains the exact tile. Physical CUR proposals are bypassed where normalized compression is needed.

The operator accumulates row and column norms and complete coefficient-error bounds in both coordinate systems. Normal, transpose and adjoint refinement require both criteria, and the final error bound includes the weighted coefficient-error terms. Stored matrices, public products, RHS and fields remain physical. Six extra real vectors cost 48 bytes per unknown; actual retained bytes, forecast ceilings, sampled admission tiles, worker serialization and scratch allowances are updated. Worker processes retain another bounded 16 MiB allowance for normalized 512-by-512 tile work; the parent forecast charges its concurrent tile scratch as well.

For the thin-layer system with nonzero magnetic contrast, its blocks are `C M^-1 S + M`, `C M^-1 K`, `B K'`, and `M-B W`. Under scaling of geometry **and layer thickness**, they have length powers 1, 0, 2 and 1. Therefore `R=diag(I,k I)` and `C=diag(k I,I)` remove their units. Identity endpoint rows use row multiplier one. This is the polarization currently excluded from hierarchical compression. The tests scale thickness along with geometry so the electrical problem stays fixed.

The small-scale legacy dielectric tile control improves from **1.53301e-7** relative field difference against Dense to approximately **1.4e-14**, including native-disabled and real two-process paths. This costs storage: at 1,200 unknowns the old TE/TM operators retained 18,489,728 / 19,296,128 bytes, versus 23,193,728 each after the fix (about 25% / 20% growth). Their 11 / 10 compressed tiles become exact tiles. The accuracy improvement must not be presented as a RAM reduction.

A larger nonlocal thin-layer holdout has 2,430 TE and 1,215 TM unknowns. Its full-field difference against Dense improves from 1.31512e-10 to **2.73531e-15**. TE retains 6 rather than 14 of 64 tiles in compressed form; operator storage rises from 80,397,536 to 88,624,688 bytes (10.2%). Peak process RSS rises from 0.187 to 0.195 GiB. Elapsed time falls from 154.94 to 103.67 seconds, but Dense takes only about 16 seconds on this modest system. This does not justify forcing compressed when Dense fits.

The thin-layer scale scan changes geometry and thickness by factors 0.01, 1 and 100. Compressed/Dense full-field differences stay near 4e-16; cross-scale difference against the large Dense reference is 7.46e-15. Uniform row/column multipliers bypass normalized decomposition because they leave relative compression error unchanged; an invariant test verifies identical payloads for that case.

## Validation and limits

The archived study contains **81 local solve attempts: 76 successful, four preliminary harness errors, and one legitimate condition-gate refusal**. This includes baseline and rejected experimental policies, not just final production. Every successful recorded solve passed its linear-system quality gate; this does not imply mesh convergence or analytic accuracy.

Independent analytic cylinder checks contain **136 case/frequency/polarization comparisons, with nine failures of the study's 0.05 dB target**. All nine are repetitions of the fixed, coarse coated TE control across scales, storage variants, baseline and preliminary source. Both old and new Dense are approximately 0.16484 dB from the analytic series there. Doubling input panels at the **same frequency** reduces the error to **0.01943 dB** (TM 0.00169 dB), supporting discretization error rather than a new factorization error. This finer one-shot result is not itself a mesh certificate. The additional `final-coated-refined-dense` run inadvertently inherited the harness's panel-dependent frequency; it is retained as a higher-frequency control and excluded from the mesh-convergence comparison.

A shared-mesh coated frequency sweep at 1.96, 2.00 and 2.04 GHz passes with disk Dense and compressed, with full-field difference **8.28e-14** and worst analytic RCS error **0.00267 dB**. The scale controls intentionally range outside the normal operating band to keep electrical size fixed while changing physical units.

- Claude regression suite: **207 passed, 0 failed** across 11 scripts. Prior Codex regression suite: **11/11 passed**. New numerical contracts: **9/9 passed**. Overlapping-request and cached-plan refresh tests pass.
- The final uniform-multiplier shortcut was added after the 207-test run. The nine focused tests, including its payload-invariance test, and a **60/60** analytic/physics subset were rerun on final source. The 60 are repeated coverage, not 60 additional unique tests.
- Actual hp-adaptive cavity runs used eight drawn primitives at 6 GHz; both backends accepted degree three on 157 panels, reported `adaptive_mesh.used=True`, `fallback=False`, and `mesh_convergence_certified=True`. Separate dielectric and coated certified workflows also passed.
- Native-disabled kernels, actual worker processes, spool transfers, known-solution normal/transpose/adjoint actions, capacity refusal, cancellation, compact-inverse allocation fallback and near-singular rejection are covered.
- Automatic with one thread selected disk Dense at 0.85 GiB and in-memory Dense at 1 GiB. Four-thread controls selected compressed at both caps because their Dense assembly forecast was 1.035 GiB; this is expected thread-dependent memory accounting. No failed Dense attempt was needed.
- Static compilation and whitespace checks pass with `core.whitespace=cr-at-eol`, preserving the base's mixed line endings. All eight changed production blobs have verified identities in `SOURCE_IDENTITY.json`.

Four preliminary harness errors are retained: two passed `mesh_strategy` in the wrong argument position, and two supplied a CCW exterior contour. Production correctly rejected the invalid calls/geometry. The portable runners are corrected, and successful CW adaptive results have distinct names. These do not count as passed controls.

The focused spool test verifies the stored factor arrays bitwise. Products are compared with a roundoff tolerance because disk decoding changes array memory order, which can change BLAS reduction rounding. Its initial bitwise-product assertion failed by only 8.8e-16 relative; that test failure is retained and the corrected coefficient-level check is reproducible.

The baseline and candidate use the same native libraries. Host: Linux, Python 3.12, NumPy 2.3.5, SciPy 1.17.0; four-CPU allocation and 16 GiB cgroup memory. These are not Windows or physical 32 GiB capacity tests. Peak RSS is the process high-water mark, not all OS file cache or a guaranteed sum of transient child peaks. Forced-worker tests exercise correctness, not performance.

**A full-size difficult model remains unqualified.** The 6.096 m (20-foot), 2 GHz star with an approximately 1 mm coating reaches an estimated condition number **2.50349e6**, above the unchanged 1e6 limit. Dense with an 8 GiB budget and disk residual storage refuses it after 288.13 seconds at 5.205 GiB peak process RSS. It emits no field array; the gate stops execution before field RHS solves. RAM was not this attempt's blocker. This production control does **not** establish that the prior audit-only block-balanced version's LU residual failure has been fixed, because that older experiment changed the conditioning path.

The 2 m coated-star control does pass (condition about 533,086; compressed/Dense field difference 2.61062e-11). This does not qualify the thinner 20-foot case. A next study should independently derive and validate closed-coating balancing, separate conditioning from field sensitivity, and compare progressively refined meshes before considering changes to that admission definition. Do not raise the condition limit to make the example pass.

The tighter initial inverse is calibrated on a limited family. More irregular/lossless shapes can pay higher storage without a timing benefit; a cost-aware choice might improve this later, but would need robust prediction and fallback tests. Normalizing inverse construction, in addition to operators, may reduce unit-dependent ranks, but is not implemented or established here. Disk-backed residuals still leave LU and working memory in RAM. The evidence continues to support both Dense and compressed, with Automatic selection; it does not establish a catch-all backend or qualify all 2–18 GHz, 20-foot desktop models.

## Evidence archive

The complete evidence archive is published beside this handoff as `evidence.tar.gz.part00`, `evidence.tar.gz.part01` and `evidence.tar.gz.part02`. Its 1,563,226 bytes contain 302 files, including 135 complete complex128 field arrays, synthetic geometries, raw solve attempts, pinned test scripts/results and Claude's repository review evidence.

Archive SHA-256: `326cec64884433cc27c16b0d9f8c9c814bb4e9f21ecfa4eba07ebe59aa7fe35c`. All part hashes and all 302 member hashes were verified before publication. Use `unpack_evidence.py` below to verify and extract the package; it checks every part and member against `EVIDENCE_MANIFEST.json`.

## Reproduction

Install the repository's GHOST requirements plus **NumPy, SciPy, psutil and threadpoolctl** for these scripts. Preserve the same native libraries in both checkouts; fallback controls explicitly disable native calls. The included tests are pinned copies, not imports from a changing Claude branch.

`SUMMARY.json` recomputes every quoted field comparison from complete complex arrays. `ANALYTIC_CHECKS.json` retains failed analytic comparisons; `RUN_NOTES.json` identifies intermediate policies, harness mistakes and timing caveats. `SOURCE_IDENTITY.json` fingerprints final production source and records the exact base. `EVIDENCE_MANIFEST.json` verifies archive parts and every extracted member, including all raw solve attempts, full emitted field arrays, Claude evidence and test logs.

From this repository checkout, with a separate checkout of the pinned base:

```sh
export GRIM_ROOT=$(pwd)
export GRIM_BASELINE_ROOT=/absolute/path/to/checkout-at-965d9417156d3f61b593310e27d17af2ea0cd19a
cd audits/codex-2026-11-12/solver-numerical-followups
python unpack_evidence.py /tmp/grim-numerical-evidence
cd /tmp/grim-numerical-evidence
python verify_claude.py
python analyze_followups.py
python analytic_checks.py "$GRIM_ROOT"

export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PYTHONPATH="$GRIM_ROOT/tools/GHOST" python test_numerical_followups.py
GHOST_AUDIT_ROOT="$GRIM_ROOT" python claude_tests/regression/run_all.py
PYTHONPATH="$GRIM_ROOT/tools/GHOST" python previous_tests/test_regressions.py
python previous_tests/test_parallel_requests.py "$GRIM_ROOT" /tmp/overlapping-results.json
python previous_tests/test_planner_refresh.py "$GRIM_ROOT" /tmp/planner-results.json

# Fresh output directory: runners skip any already-recorded nonempty result.
export GRIM_EVIDENCE_DIR=/tmp/grim-numerical-rerun
python run_validation.py
python run_benchmarks.py
python run_holdouts.py
python run_final_extras.py
python run_mesh_control.py
python analyze_followups.py
python analytic_checks.py "$GRIM_ROOT"
```

Run the benchmark scripts sequentially, with other solver workloads stopped. Each solve runs in a fresh process with a 360-second harness limit; inspect raw `error` and gate fields rather than relying on process exit status. The original 20-foot condition refusal is expected, not a passing field control. `run_initial.py` reproduces preliminary mechanism controls; their intermediate-source results are preserved separately and are not expected to be bitwise reproducible from final source. The probe-policy experiments use explicit audit-only hooks to reproduce rejected variants. No audit script is imported by production.

## Questions for Claude's second audit

1. Independently verify Dense's normal/transpose/adjoint transformations and the ordering of spool, scale, factor and restore. Check that no original coefficients are overwritten before they are preserved.
2. Review the scaled 1-norm refinement criterion and its bounded correction policy against the physical infinity-norm release gate, including zero RHS, nonfinite candidates and the near-singular refusal control.
3. Derive the nonlocal thin-layer row/column multipliers and endpoint exceptions independently. Check both coordinate systems' full-tile bounds, including transposed coefficient errors and process/spool transfers.
4. Reproduce the condition-timer duplication and the controlled inverse-initialization comparisons. Assess the 4,096-unknown performance threshold and compact fallback without relying on the rejected probe relaxation.
5. Review the holdouts and unresolved limitations below before calling this a distribution qualification. No failed study control or time limit should be omitted.

Publication builds on the complete 730-blob production base tree; Claude's branch supplies evidence rather than replacing production files. Source identity, summaries, raw results, full field arrays, pinned regression copies and reproduction scripts accompany this report.
