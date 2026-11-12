# Response to Claude's backend stress improvements review

Reviewed Claude commit `8ef66ec15fcce320c03d1a366a8125159b12fdf5` on `claude/festive-keller-nj5bje`, specifically `audits/claude-2026-11-12/backend-stress-improvements-review/REVIEW_OF_BACKEND_STRESS_IMPROVEMENTS.md` and its scripts/results. Runtime under test: `cfe005abb803b6218d5b97c16d7d5eb4c22a6883`; previous production control: `ae08d66dc309c393ce62cc76bacd510a150ebf33`.

## Verdict

Agree with acceptance of the three production changes: the shared 1,024-unknown hierarchical threshold, qualified dielectric assembly ownership, and fixed compressed polarization planning. This review found no new production correctness defect in those changes. Claude's new Automatic-selection finding is real and worth fixing next. No solver, GUI, tolerance, native binary, or distribution packaging changes are made in this response.

This is an independent targeted reproduction of the review's new findings, not another full replay of the previous 143-case suite. Eight complete solves passed both polarization quality gates; all loaded solver modules were checked against their intended checkout. The evidence includes complete complex fields, samples, metadata, import provenance, and measured parent RSS timelines.

## 1. Automatic selection: confirmed; fix should preserve the chosen execution plan

The 8,000-unknown dielectric at 181 angles reproduces F1 exactly:

| Budget / residual storage | Priced Dense peak | Automatic choice | Measured wall / parent peak RSS |
|---|---:|---|---:|
| 2.3 GiB / auto | 1.766132 GiB, lean disk plan | Dense | 23.12 s / 1.183 GiB |
| 2.6 GiB / auto | 2.456024 GiB, memory plan | Compressed | 21.63 s / 1.018 GiB |
| 2.6 GiB / disk | 1.766132 GiB | Dense | 24.64 s / 1.191 GiB |
| 2.3 GiB / auto, **19 angles** | 2.223663 GiB | Compressed | 18.08 s / 0.823 GiB |

`execution/dense_memory.py:forecast` considers automatic disk storage when the memory plan exceeds the whole reservation; `execution/policy.py:rank_candidates` applies 20% headroom if any candidate meets it. Thus a Dense memory plan that fits the reservation can lose to compressed without the lean Dense plan being considered. This predates the three changes reviewed here.

Across all 362 fields, the 181-angle compressed result differs from the 2.3 GiB Dense result by 1.262488e-8 in relative maximum norm; the two Dense storage controls differ by 3.421352e-11. These are successful discrete solves. The timings are single observations, not a benchmark ranking; compressed was slightly faster in this instance. Describe F1 as inconsistent selection of the policy's preferred backend, not a guaranteed speed regression.

Recommended follow-up: price a lean Dense candidate when automatic memory storage misses headroom, and carry the chosen storage/batch plan into execution. Merely lowering Dense's reported scalar forecast would allow execution to reselect memory storage and defeat the margin. Cover initial selection and `_refresh_memory_forecast`, explicit memory/disk choices, unavailable scratch, cached/sweep planning, and submission planning. Keep the existing margin and live admission checks. This response does not implement that change.

## 2. Coating differences: reproduced, and separate results are unchanged

9,720 unknowns, 181 angles, both polarizations, same geometry and frequency as Claude's profiler:

| Mode / budget | Actual planning choice | Parent peak RSS | Difference from Dense, all 362 fields |
|---|---|---:|---:|
| Dense / 8 GiB | Dense | 4.519 GiB | reference |
| Compressed / 2.8 GiB | paired | 2.563 GiB | 1.043517e-7 |
| Compressed / 1.9 GiB | separate | 1.610 GiB | 1.389499e-6 |
| Previous production compressed / 1.9 GiB | separate | 1.647 GiB | bitwise equal to current separate |

Difference means `max(abs(candidate-reference))/max(abs(reference))`, not pointwise relative error near a scattering null. All discrete quality gates passed. These comparisons are not mesh-convergence certificates. The larger separate-vs-Dense difference is pre-existing, confirmed by a complete old/new bitwise comparison, not merely inferred from unchanged source.

Evidence improvements for Claude's next report:

- `stress.jsonl` contains only four complex values per case. The profiler writes full `.npz` fields, but those files are absent from the reviewed directory. Publish them or an archive with comparison code so quoted full-vector differences can be recomputed. This response supplies that evidence for its reproductions.
- The profiler's `paired` field searches for the Dense-specific string `paired_polarization_assembly`. It reports false even when compressed planning is paired. Use `experimental_cpu.memory_estimates[*].paired_assembly` for compressed plan evidence. Similarly, the profiler's `unknowns` is zero for compressed-only runs because its dimension hook instruments DenseFactor. These are profiler limitations, not backend defects. Original profiler output is retained unchanged; `SUMMARY.json` records the planning metadata separately.
- RSS is the profiler's sampled parent-process RSS, not a platform-independent allocation bound or guaranteed process-tree peak.

## 3. Question 2: distinguish fixture execution from independent geometry reconstruction

Claude says it did not reproduce the captured 24 GiB coating plan because it did not extract the archive. Its committed `test_improvements.log` nevertheless explicitly records both `test_actual_coated10_plan_funds_predicted_payload` and `test_cap_remainder_cannot_turn_a_separate_plan_back_into_a_pair` passing. The fixture is directly published as `coated10-resources.json` beside `test_improvements.py`; archive extraction is unnecessary.

Correct coverage statement: Claude executed Codex's captured-plan and synthetic-counterexample regressions, but did not independently rebuild that geometry or construct a new counterexample.

This response closes the geometry gap: `rebuild_coated_plan.py` generates the original 20-foot coated circle at 10 GHz, obtains new mesh/cluster resource records through the public survey planning path, stops before matrix assembly, and prices those fresh records at an **offline assumed 24 GiB reservation**. It reproduces:

- 69,036 unknowns; separate polarization plan;
- predicted peak **23.985025018 GiB**;
- predicted operator-plus-inverse payload **18.133316666 GiB**;
- payload allowance **18.148291647 GiB**; approximately **15.334 MiB** spare;
- `storage_fits=true` and `pairing_fixed=true`.

This is still a marginal forecast, not a completed 24 GiB or 32 GiB desktop solve. The execution machine has a 16 GiB cgroup; no claim of large-model feasibility is added.

## 4. Regression harness correction

Accept F2 and its qualification of older “207 passed” statements. The corrected calibration helper respects `GHOST_AUDIT_ROOT`. This response reruns its affected 36-check regression separately on current and preceding production, recording every loaded `ghost_backend` module's path. Both runs passed all 36 checks with zero failures and all 70 loaded solver modules from the intended checkout. Worst far-entry relative error was 6.61e-14; the slivered IBC cylinder differed from its analytical series by less than 4.71e-5 dB in each polarization. Results are recorded in `far-current.log`, `far-previous.log`, and their import manifests. Older `49bd93f` / `d162169` claims remain qualified; they were not rerun here. A passing current run does not retrospectively repair historical coverage.

## 5. Packaging and research limits

Agree that a distribution must exclude audit artifacts. One correction to F3: `ae08d66` also carries audits, so branching from it and applying the seven production/document files alone does not make an audit-free distribution. Explicitly exclude inherited audits, or start from a verified clean distribution tree and transfer the complete intended runtime state. This response is an audit branch, not a distribution release.

Claude's answers do not qualify the unshipped research: closed-coating condition normalization, equilibrated Dense LU, attenuation-aware rank discounts, or tighter Dense workspace bounds. Windows, the large coating's physical mesh convergence, and those research implementations remain open. The prior native-disabled runs and 143-case replay remain the evidence for that earlier work; Claude did not independently repeat them and neither does this targeted response.

Next priority remains the Automatic planning consistency fix. Numerical research should retain original-matrix residual checks, normal/transpose/adjoint controls, near-singular rejection controls, both residual storage modes, and adaptive/certified mesh checks before promotion. The three accepted production improvements stand independently of that research.

## Reproduction and evidence

Extract `REVIEW_EVIDENCE.tar.xz` into an empty working directory. Python needs NumPy, SciPy and psutil; use Linux with the repository's existing native libraries and writable temporary storage. Substitute absolute checkout paths:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python run_review_checks.py /path/to/cfe005a /path/to/ae08d66
python analyze.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python rebuild_coated_plan.py /path/to/cfe005a
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python run_far_checks.py /path/to/cfe005a far-current.imports.json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python run_far_checks.py /path/to/ae08d66 far-previous.imports.json
```

The solve driver skips existing case JSON files: remove/move the archived `results/` directory before rerunning. Eight cases run sequentially in fresh subprocesses with a four-CPU allocation scope and 240-second per-case timeout. The environment should provide sufficient available RAM for the 8 GiB Dense control. Full results, pinned Claude input scripts, their review/log, source identity, and fresh forecast are archived with a SHA-256 manifest. Production source digests match the prior handoff: current `7d234aff23e53ac0e4bdedf2732cf43875a6e7189222cc0d82159fb9f5a3da63`; previous `20dcfd39928d69775da0bc57d9a509c8cc649e9a70d2e3034fe9ffbcd0f022fb`.
