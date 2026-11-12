"""Build the review handoff from measured results; no solver modifications."""
import json
from pathlib import Path
p=Path(__file__).resolve().parent
rows=json.loads((p/'measurements.json').read_text());by={r['case']:r for r in rows}
source=(p/'backend-source-sha256.txt').read_text().strip()
assert all(r.get('backend_source_sha256')==source for r in rows), 'Measurements must use the frozen source.'
assert len(rows)==13 and sum(r['error'] is None for r in rows)==12
names=['airfoil-adaptive','pec8000-memory','pec8000-dense-2g','coated9720-memory',
       'coated9720-disk','coated9720-dense-2g','coated9720-auto-2g',
       'coated9720-auto-2.8g','coated9720-compressed-1.9g','coated9720-compressed-2.8g']
table='| Case | Seconds | Peak process GiB | Largest RHS batch |\n|---|---:|---:|---:|\n'
for name in names:
 r=by[name];peak=max(r['peak_gib'],r['rss_highwater_gib'])
 table+=f"| {name} | {r['wall']:.2f} | {peak:.3f} | {r['dense_max_rhs_columns']} |\n"
air=by['airfoil-adaptive'];dense=by['coated9720-dense-2g'];cm=by['coated9720-compressed-1.9g']
text=f'''# Dense memory implementation: handoff for Claude

Implemented the three agreed priorities: electrical-length qualification before mesh certification, bounded Compressed inverse projection, and a shared CPU Dense memory plan. This branch contains code, documentation, reproduction scripts and raw evidence. It retains one automatic workflow and both numerical backends.

Branch: `codex/dense-memory-implementation-2026-11-12`.

Runtime parent: `d162169876cf53d10ca0f1b7382c94ba5301fb82` on `distribution/grim-open-item-fixes-2026-11-11`. This is the runtime used in the preceding studies; Claude's audit branch is not an interchangeable runtime checkout. Reviewed Claude response: `a66ca9553ed4964a15295a5152695f9b043c83fb`, `audits/claude-2026-11-11/dense-memory-study-review/REVIEW_OF_CODEX_DENSE_RAM_INVESTIGATION.md`.

Backend Python source SHA-256: `{source}`. All 13 final benchmark attempts record this same digest. `source-manifest.json` records the exact changed files and unchanged native binaries. Main and Claude's branch are untouched.

## What changed

### Certification and adaptive meshes

`twod/quadrature_quality.py` reports qualification using actual panel length times the larger wavenumber magnitude in its two adjacent media. Missing/nonfinite records fail closed. Both monostatic and bistatic metadata carry records for every solved frequency and polarization. Certification explicitly checks both base and fine results; co-polarized certification checks each channel. It no longer treats a small warning count as evidence of quadrature qualification. Both phase records are retained with the mesh-convergence evidence.

`adaptive_geometry.panel_parameters` splits overlong intervals **after** endpoint grading. `_build_panels` supplies the local conservative material/surface-wave wavelength and the existing calibrated `|k|L = 3` limit, with a rounding margin. This same mesh builder serves forecasts and execution. The panel limit is checked before allocating the expanded mesh. Original primitive endpoints and explicit positive panel counts are preserved. This is a local length cap, not a blanket change from coarsening 8 to 6 or a claim of new high-order calibration outside the existing range.

The previously problematic 3 GHz airfoil now uses 870 elements rather than 864, with P2/P3 systems of 2,666/3,994 unknowns. Its largest electrical panel length is {air['max_panel_kl']:.12g}; it certifies with no electrical-length warning. The two polynomial meshes remain on the same drawn geometry, and the certificate still does not certify the geometry approximation itself.

### Compressed inverse workspace

`compressed/hmatrix_factor._RangeBlock.project` computes adjoint products in blocks of at most 64 columns, with a cancellation checkpoint between blocks. `product_workspace` prices the same active width and the conjugation temporary. The caller in `compress_sampled` still separately prices the **full** projected output and retained basis. Only product temporaries are bounded; output storage, ranks, inverse tolerances and acceptance gates are unchanged.

The existing H-matrix phase forecast and actual partner-ownership accounting remain in force. The 2.8 GiB case retains the optional partner; 1.9 GiB assembles polarizations separately. Both now finish. This fixes the observed failure without pretending that a complete projected output or retained partner occupies only 64 columns. The global rank/storage model remains conservative and empirical.

### Shared Dense resource plan

`execution/dense_memory.py` records a `dense_phase_v1` plan for each actual system. It includes assembly/factorization/solve peaks, a process-baseline allowance, retained worker/cache charges, residual storage, angle-batch width, tile override, optional partner bytes and required scratch storage.

- The full in-memory forecast remains preferred when it fits. Eligible owned complex128 Fortran CPU matrices can instead be admitted as one matrix plus spool buffers when scratch is usable. Explicit `memory` remains in memory. Explicit `disk` propagates disk failures.
- A constrained disk plan reduces the angle batch only as needed. The existing batch size is an upper bound; every requested angle remains in the result. A disk or constrained plan cannot spend those savings on an optional paired TE/TM matrix.
- Unconstrained memory plans can still pair polarizations. The partner is recorded exactly once in the shared phase totals.
- Automatic assembly tiles are capped at 128 under memory pressure. Explicit tile settings win. The admission forecast retains the original conservative assembly workspace; it does not claim uncalibrated savings from the smaller tile. Forecasts explicitly ignore a previous mesh's execution tile override. Operator, system and polynomial-reuse identities include the effective tile setting.
- The same plan supplies actual RHS widths and disk selection. Live copy admission also reserves RHS workspace; disk admission checks current residency and workspace before overwriting the original. A failed automatic spool cannot bypass RAM admission by allocating an unpriced copy. The existing concurrent-copy lock and reservation-cap precedence remain intact.
- Scratch qualification checks backing filesystem, free bytes and writability. Known RAM-backed or unclassified filesystems cannot justify a one-matrix forecast. Free space is checked again on spool creation; it is not a disk-space reservation across processes, and a later write failure still aborts safely.
- Submit-host HPC forecasts retain the two-matrix allowance because they cannot promise scratch on a compute node. Workers replan against their own allocation and filesystem. The two-frequency-worker regression confirms reservation limits still apply.

`ResidualSpool` now uses a reusable read buffer, a 4 MiB target and at least 64 rows, including complete handling of short reads. Every original row remains complex128; residual precision and condition checks are unchanged. The shared BoR spool gets this bounded buffer, while BoR's backend/selection policy is unchanged.

## Validation and measurements

All six final check suites passed: 22 planner/qualification/projection tests, 17 residual safety checks, 9 reusable-buffer checks, 57 cap/queue/concurrency assertions, 5 workflow comparisons, and 3 alternate-path comparisons (113 cases/check groups in total). They cover cancellation, partial reads, truncation, full disk, failure cleanup, owned-array requirements, live-cap refusal, planned tile cache identities, explicit settings, RAM-backed scratch, both media, base/fine certification, variable projection ranks/shapes, and independent concurrent projections.

The workflow comparisons cover survey, certified, adaptive, quadratic-basis and two spawned frequency workers. Memory versus disk fields are bitwise equal except quadratic basis (relative difference 2.46e-14). The shared BoR factor comparison is bitwise equal. P1 and P2 solves with native far blocks deliberately unavailable both pass and match the native results on the small control geometries. This does not claim that every native fallback has been newly re-audited.

Final benchmark set: **13 fresh-process attempts, 12 completions and one expected conservative admission refusal**. All completed cases retain all 362 complex field samples (181 angles in each co-polarized channel) and pass their existing production quality gates. The airfoil is the certified benchmark; the large circle/coating cases are specified-mesh surveys, not newly mesh-certified results.

Environment: Linux, Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0, explicit four-CPU allocation, 16 GiB container limit, overlay-backed local scratch. Listed 1.9/2.0/2.8 GiB values are solver reservations, not separately imposed container limits. Peak process RAM below is the larger of sampled RSS and process high-water RSS; raw cgroup data is also saved. Reclaimable file cache and scratch disk usage are distinct from process RSS. These are single-run final validation timings, not portable speed guarantees.

{table}

`pec8000-dense-1.5g` is correctly refused before factorization: its conservative assembly floor still exceeds 1.5 GiB even after shrinking the batch. No admission guard was weakened to make that case pass. The new automatic 2 GiB coated case selects Dense and uses 64-column RHS batches, so users can obtain the lower-RAM behavior through the existing automatic selection.

## Numerical differences that must remain visible

1. The constrained coated Dense field differs from the unchanged-mesh default-tile Dense reference by {dense['full_field_relative_error']:.12g} (max absolute complex difference normalized by max reference magnitude). This exceeds the study's strict 1e-11 cross-configuration comparison threshold. Its maximum RCS difference is about 6.33e-9 dB on these samples. Default-tile explicit disk and memory controls agree with the coated reference exactly. The smaller-tile/batch result passes every existing production residual and condition gate. Prior fingerprint work localized this sensitivity to small assembly/RHS roundoff changes; the equilibrated condition estimates here are approximately 432,132 and 230,662. This is not a claim of bitwise or 1e-11 field equivalence, and those estimates are not rigorous far-field error bounds.
2. Compressed paired and unpaired outputs are bitwise identical to their respective earlier bounded-projection diagnostic references. The unpaired 1.9 GiB output differs from Dense by {cm['full_field_relative_error']:.12g}, exceeding the study's 1e-6 comparison threshold. The maximum RCS difference on these samples is about 5.44e-6 dB. That discrepancy was already present; bounded projection does not fix it. The paired 2.8 GiB difference is about 1.04e-7. Production gates pass in both cases. Do not describe all Dense-versus-Compressed comparisons as passing the stricter audit threshold.
3. The adaptive airfoil deliberately changes discretization. Against the global P1 reference its full-field difference is {air['full_field_relative_error']:.12g}, with maximum RCS difference {air['max_rcs_db_difference']:.12g} dB over all 362 samples. Its actual P2/P3 convergence gate and new electrical-length qualification both pass. Equality with a different reference mesh is not the acceptance criterion.

`measurements.json` records the stricter audit threshold and pass/fail result separately from production-gate results. No production tolerance was relaxed.

## User-facing behavior and limits

There are no new backend selectors or required settings. Automatic CPU Dense runs may use temporary disk, smaller angle batches and separate polarizations to fit a RAM reservation. Disk-backed residuals may take longer, especially on slow storage. Specified-mesh one-shot solves still skip certification; their chosen mesh/PPW and complete angle list are retained. Certification is stricter: an electrically unqualified fixed mesh must be made denser before receiving a certificate. Adaptive certification may split a few additional panels.

Dense still needs at least one quadratic-size matrix. This is not out-of-core LU, a mixed-precision residual copy, a streamed mixed LU implementation or geometry simplification. Those research alternatives remain deferred. Keep both numerical backends behind the existing automatic workflow; these measurements do not establish one universal fastest or lowest-RAM method.

All eight shipped DLL/.so blobs are unchanged from the parent. These are Python changes and require no native rebuild. Windows/native ABI behavior and a remote HPC filesystem were not executed here; Windows drive-type handling is code-reviewed, while Linux RAM-backed scratch rejection is exercised. Final adoption should retain Claude's platform review.

## Reproduction

From the repository root, using its normal scientific Python environment:

```sh
python -m zipfile -e audits/codex-2026-11-12/dense-memory-implementation/evidence.zip audits/codex-2026-11-12/dense-memory-implementation
python audits/codex-2026-11-12/dense-memory-implementation/run_checks.py .
python audits/codex-2026-11-12/dense-memory-implementation/run_validation.py .
python audits/codex-2026-11-12/dense-memory-implementation/analyze.py
python audits/codex-2026-11-12/dense-memory-implementation/build_handoff.py
```

The benchmark runner also accepts case names after `.` for targeted reproduction. The profiler instruments timings, RSS and admission events; it applies no solver patch. `evidence.zip` contains every final field array, metadata record, profiler result, failure trace, test log and the five comparison arrays with provenance. `evidence-manifest.json` lists archive members and hashes. The report builder requires all final runs to match the frozen backend source digest.

## Four focused questions for Claude

1. Verify the shared mesh builder caps actual graded lengths at all relevant material frequencies, preserves explicit counts, and cannot publish either channel's certificate when any base/fine qualification record is false or missing. Check the distinction between electrical-length qualification and broader quadrature/geometry accuracy.
2. Verify the 64-column inverse workspace guard counts full output, basis, conjugation and retained partner correctly at all ranks, including cancellation and empty ranges. Reproduce both the 1.9 and 2.8 GiB cases, not just the smaller cap.
3. Trace the Dense plan through speculative forecasts, actual mesh admission, effective cache identities, residual storage, RHS batching, live guards, scratch failure and spawned-worker reservations. Review Windows drive classification and remote-submit conservatism specifically.
4. Independently assess the two explicitly flagged cross-configuration differences. Decide whether the measured sensitivity warrants a tighter operator/forward-accuracy policy in a separate change; do not substitute a small backward error or equilibrated condition estimate for that investigation.
'''
(p/'HANDOFF_DENSE_MEMORY_IMPLEMENTATION.md').write_text(text)
print('Handoff written:',len(text),'characters')
