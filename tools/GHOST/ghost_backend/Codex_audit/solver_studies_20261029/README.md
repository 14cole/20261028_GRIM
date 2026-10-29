# 2D solver capacity, accuracy, performance and lifecycle studies

Source revision: `4b0bfba12870f52c95317439d12c7f46958d7c25`. The user authorized representative shapes and materials, up to 15 GHz on a 32 GB machine. This study does not add the declined refinement-preview feature or change production solver code. Experimental algorithms remain confined to the audit runner.

The evidence supports **keeping dense and compressed behind Automatic**. Representative 12 ft × 3 ft metal and moderate-dielectric inlets certify through 15 GHz within the machine's RAM. Coated and strongly contrasting materials remain materially harder: conditioning, inverse compression and conservative admission can block them before physical memory is exhausted. The following results identify exactly which cases passed and which did not.

## Method and limits

- Synthetic inlet outlines are 12 ft by 3 ft. The ordinary notch is 4 ft deep and 1 ft wide; the narrower outline used in repeated comparisons is 6 ft deep with a 3-inch mouth. The dogleg contour adds internal turns. Raw coordinates and material definitions are saved with every request.
- The material-filled body uses epsilon 4 - 0.04i, mu 1. The coated inlet instead has a metal core and a dielectric shell, epsilon 2.5 - 0.05i, mu 1. Its initial shell thickness is 1/8 inch. These are physically different model types.
- Capacity cases request a 24 GiB solve budget; matched performance cases use 12 GiB, and the learned-hint comparison uses 8 GiB. Production admission still uses live available RAM. No availability override is used for numerical solves. The machine exposes 31.10 GiB physical RAM, with other applications consuming part of it.
- Isolated case monitors sample parent and descendants every 0.1 s, with a 24 GiB RSS/private-commit ceiling, a 2 GiB host-available-memory floor and an eight-minute case limit. A guard stop is an unfinished experiment, not proof of mathematical impossibility. RSS sums can count shared pages more than once; Windows private bytes are commit, not resident RAM.
- Certified capacity/performance solves retain 361 angles, both polarizations, existing conditioning/physical-error/sample-row checks and mesh convergence. Four assembly/BLAS threads are requested. Timing comparisons run serially, alternate mode order, and use independent empty timing histories. Reported ranges describe these repetitions, not statistical confidence intervals.
- Stage observations are sampled and inclusive; overlapping stages must not be added together. Initial forecasts must not be compared with later refined meshes as though they were forecasts of the same system.

## Completed initial capacity trials

| Shape/material | GHz | Outcome | Solve time | Peak RSS |
| --- | ---: | --- | ---: | ---: |
| Moderate material-filled inlet | 3 | Certified | 4.00 s | 0.542 GiB |
| Moderate material-filled inlet | 10 | Certified | 57.95 s | 4.585 GiB |
| Moderate material-filled inlet | 15 | Certified | 151.10 s | 9.960 GiB |
| Dogleg metal inlet | 15 | Certified | 42.59 s | 5.401 GiB |
| Metal inlet with 1/8-inch dielectric coating | 3 | Conditioning rejection: 8.55e6 exceeds 1e6 | — | 5.769 GiB |
| Same thin-coated inlet | 10 | Stopped at eight-minute guard during reference-path work | — | 10.980 GiB |
| Same thin-coated inlet | 15 | Hierarchical inverse rank rejection | — | 6.150 GiB |

The moderate dielectric's 15 GHz result closes a prior evidence gap: this particular system fits and certifies. It passes its initial P2/P3 comparison at 2,904 panels, reaching 17,424 system unknowns without further spatial refinement. The two earlier metal contours' approximately 3.3x refinement growth did not predict this case. Its final backend is dense.

The thin-coated failures demonstrate that RAM capacity is not the sole constraint. The 15 GHz traceback reaches the inverse's sampled off-diagonal compression: its local cap is half the smaller block dimension (214 here), distinct from the global maximum rank of 2,048. The existing rejected-block dense-leaf fallback accepts nodes only through size 512. A separately labeled audit experiment tests a limit of 1,024, within the existing 16 MiB coefficient-query bound, without changing accuracy gates. Its incomplete outcome is reported below; no production change was made.

## Independent accuracy checks

Seven new cases completed 13 certified mode-specific solves: PEC, moderate dielectric and thin-coated circular cylinders at 15 GHz; a 3-ft-diameter PEC cylinder at 15 GHz; and three frequencies bracketing the tenth J0 zero for a 0.1 m-radius PEC cylinder. All use both polarizations. Dense and compressed are checked separately except for the largest PEC case, which uses compressed. The hierarchical threshold is lowered only within these small-fixture experiments to exercise that path.

All cases pass the unchanged solver gates and independent circular-wave series comparisons. The largest RCS error is **0.01230 dB**, below the preselected 0.05 dB audit limit. Independent complex-amplitude checks on PEC cases remain below **0.08884%**, below the 0.5% audit limit. Material/coating series checks here compare scattering magnitude; they do not independently certify phase. Circle chord approximation remains part of the comparison error. Fixed source panel counts can route the requested adaptive policy to reference-mesh certification; metadata records that choice.

## Repeated solves and cancellation

The coated-fixture lifecycle test completes 15 solves over three frequencies, followed by cancellation/restart pairs at operator construction, inverse construction and field solving. Repeated/restarted fields agree with their standalone baseline within rtol 1e-10 and atol 1e-12. After every request, hint state, preparation state and metrics state are cleared; no worker processes, solver Python threads, retained worker reservation or additional temporary paths remain.

Post-warm-up RSS spans **2.156 MiB** across repeated completed solves. This is evidence against accumulating growth in this bounded small-fixture run, not proof of leak-free overnight operation for every large geometry. Separate worker-process loss and preparation-failure regressions are included in the planned test run.

## Repeated dense/compressed/Automatic comparison

All rows below use the same 12 GiB budget. Time is the median, followed by the observed range; RSS is the observed range. Every run certifies, and each geometry reaches the same final mesh across modes.

| 15 GHz metal shape | Mode | Repeats | Seconds: median (range) | Peak RSS, GiB |
| --- | --- | ---: | ---: | ---: |
| Ordinary inlet | Dense | 3 | 86.40 (86.35–86.42) | 9.656–9.667 |
| Ordinary inlet | Automatic | 3 | 87.09 (87.02–87.16) | 9.659–9.663 |
| Ordinary inlet | Compressed | 3 | 125.31 (125.27–125.38) | 2.255–2.283 |
| Narrow inlet | Dense | 2 | 114.59 (114.44–114.74) | 8.485–8.504 |
| Narrow inlet | Automatic | 2 | 115.36 (115.22–115.50) | 8.495–8.520 |
| Narrow inlet | Compressed | 2 | 140.33 (139.76–140.89) | 2.610–2.613 |

Dense saves about 39 seconds (31%) against compressed on the ordinary inlet, and 26 seconds (18%) on the narrow inlet. These savings are below two minutes, as the user suspected, but they also occur at 15 GHz. Compressed reduces peak RSS by roughly 76% and 69%, respectively. Automatic chooses dense under this budget and closely follows its time. The largest normalized complex-field difference between these dense/compressed repetitions is 8.38e-13; agreement between implementations is supplemented by the independent cylinder checks above.

**Keep both backends behind Automatic.** Dense has a repeatable speed advantage; compressed has a substantial memory advantage. Automatic is a selection policy, not a third independent numerical factorization. The evidence supports retaining these two implementations, rather than adding further user-facing modes. These measurements establish benefits, not a quantitative estimate of annual maintenance cost.

Three alternating hint-on/off pairs on the high-contrast 1 GHz inlet give medians of **34.07 s with hints versus 39.11 s without**, a **12.9% reduction**. Factor-build calls fall from eight to five in every pair. Normalized field difference remains below 5.64e-16. RSS ranges overlap, so the strongest result is time/build savings, not a large RAM saving. Hints remain request-local; this study adds no persistent hint or solve database.

## RAM budget and forecast interpretation

Two additional ordinary-inlet runs explore existing memory controls. They are single probes, not repeated timing estimates:

| Request | Result | Seconds | Peak RSS |
| --- | --- | ---: | ---: |
| Dense, 8 GiB budget | Certified, dense final mesh | 104.63 | 3.991 GiB |
| Automatic, 6 GiB budget | Certified, compressed final mesh | 98.30 | 3.702 GiB |

The smaller dense budget suppresses optional memory optimizations and trades about 18 seconds for substantially lower residency relative to the 12 GiB repeated dense median. Automatic can use dense earlier and compressed on the larger mesh; its final mode does not describe the entire run. A forced-compressed moderate-dielectric 15 GHz probe also certifies in **161.97 s at 3.987 GiB**, compared with **151.10 s at 9.960 GiB** for its Automatic/dense counterpart. Their normalized field difference is at most 2.59e-8. This is a promising memory/time tradeoff on one material fixture, not a repeated universal speed ratio.

The base dense forecast is not a prediction of all optional resident allocations. At the final ordinary-inlet mesh it is about 6.094 GiB, while the 12 GiB-budget run peaks near 9.66 GiB. Paired polarization assembly can retain a partner matrix, and hierarchical factorization can admit an ordered matrix copy separately against live headroom and the request reservation. The ordinary-inlet copy is 3,269,552,400 bytes; the narrower geometry's copy is 4,019,052,816 bytes, and the TE copy is declined while its partner matrix is resident. This explains why a larger system can have a smaller observed peak. See `twod/assembly/session.py::plan_paired_assembly`, `linalg/hierarchical.py::ordered_copy`, and `linalg/residual_spool.py::copy_fits` in the audited revision.

For the moderate dielectric, the largest selected-mesh base forecast is 8.678 GiB, and the admitted ordered copy is 4,857,532,416 bytes; the observed peak is 9.960 GiB. These discrepancies warrant clearer diagnostic accounting of base forecasts, optional allocations and observed peaks. They do **not**, by themselves, prove that admission is unsafe. Do not discount conservative compressed admission forecasts from a handful of successful cases. Initial-mesh forecasts must also remain distinct from final refined sizes.

## Capacity extensions and smaller-preconditioner experiment

| Additional case | Outcome | Peak RSS |
| --- | --- | ---: |
| Coated inlet, 15 GHz, experimental dense-leaf limit 1,024 | Eight-minute guard; no certified result | 9.051 GiB |
| Half-inch coating, 3 GHz | Condition estimate 1.26648e7 exceeds 1e6 | 5.707 GiB |
| One-inch coating, 3 GHz | Condition estimate 9.29355e6 exceeds 1e6 | 5.687 GiB |
| High-contrast material-filled inlet, 3 GHz | Preflight RAM refusal | 0.118 GiB |
| High-contrast material-filled inlet, 15 GHz | Preflight RAM refusal | 0.286 GiB |

The experimental dense-leaf run reaches solving, far-field evaluation and conditioning stages, then another preparation/operator phase before its guard stops it. It does not establish an end-to-end fix. The in-memory fallback-event list was only scheduled for writing on worker exit; the guard kills the worker, so the exact number and sizes of fallback leaves are unavailable. Do not claim measured leaf-level savings from this run. A follow-up should flush that telemetry incrementally and isolate the conditioning issue before considering production adoption.

The high-contrast fixture uses epsilon 101.19 - 11.88i and mu 3.45 - 3.47i as constant synthetic inputs, not a measured broadband material model. At 3 GHz the forecast is 39.32 GiB dense / 20.92 GiB compressed against 14.78 GiB live admission capacity. This does not prove that compressed cannot fit a more idle 32 GB machine. At 15 GHz the forecasts are 935.84 / 474.48 GiB against 14.66 GiB capacity. Those are conservative predictions, not observed allocations, and no forced over-budget solve was attempted. These cases remain unsupported under the current policy and available memory.

The local/coarse prototype completed all six variants: 128-entry block Jacobi, 512-entry block Jacobi and 128-entry blocks with a coarse correction, each for TE and TM. It uses the global compressed operator on a fixed 4,096-unknown high-contrast 1 GHz system and two seeded synthetic right-hand sides. This is an algebra experiment, not a mesh-certified 15 GHz physical solve.

**None of the six variants passes.** Every right-hand side reaches the 400-iteration limit. Full-oracle-row backward errors range from 3.91e-9 to 6.08e-6, above the 1e-12 target; normalized solution differences range from 6.12e-5 to 3.85, above 1e-8. The preconditioners occupy 8.05, 32.05 and 12.11 MiB, respectively, versus about 39.25–39.34 MiB for the existing inverse. However, the retained operator still occupies 120.46 MiB, and each iterative solve also needs its Krylov workspace (at least 2.56 MiB for the stored basis here). Factor payload reduction therefore overstates whole-process savings.

Existing-inverse build plus solving both synthetic right-hand sides takes 0.43–0.44 s after operator construction. The unsuccessful alternatives take 9.07–18.15 s for iteration alone, plus their small build costs. Their independent full-row verification is additional and excluded from those iteration timings. The entire monitored prototype peaks at 0.525 GiB RSS. This negative result argues against shipping these particular simple preconditioners; it does not rule out more capable iterative methods or longer iteration limits on other problems.

## What doing the solve in chunks can and cannot accomplish

The current solver already bounds coefficient queries and assembles blocks; it can batch right-hand sides/angles. Its dense residual spool writes the original coefficients to disk and reads row blocks for residual checks. Compressed polarization storage can leave the unused partner on disk until needed, and retained polynomial-operator storage can temporarily move a completed operator to disk between polynomial solves, then restore it. These mechanisms reduce particular overlapping allocations. They do not provide a general disk-backed inverse, and the restored operator must fit when used.

The scattered field is globally coupled: solving isolated pieces independently does not produce the same solution. A scalable alternative must retain the interactions between pieces, for example by applying the global operator in blocks and using an iterative method with a smaller preconditioner. The audit prototype above tests one such direction. Smaller blocks alone do not guarantee convergence, and extra iterations may erase the speed benefit. Disk storage also trades RAM for I/O; it cannot cure poor conditioning or high compression ranks. On the present evidence, use existing budget controls and compressed first, and keep new iterative/out-of-core methods experimental until they pass the same accuracy and convergence requirements.

## Recommended next work

1. **Retain dense, compressed and Automatic selection.** Keep Automatic as the normal workflow. The repeated comparisons give each backend a measurable role; they do not justify another user-facing mode.
2. **Prioritize coated-interface conditioning.** Isolate which polarization, interface spacing, scaling and discretization cause the rejected condition estimates. Compare against an independent solution before changing equation scaling or quality criteria. Successful coated circles and unsuccessful coated inlets make this a useful geometry-sensitive study.
3. **Improve diagnostic RAM accounting.** Separate base mesh forecasts, optional paired/copy allocations and observed stage peaks in internal evidence. Test tightly limited reservations across refined meshes. The user declined the hypothetical tripling preview; no replacement preview is proposed here.
4. **Qualify local dense fallback before adoption.** The larger-leaf experiment has no certified success. Add incremental fallback telemetry, repeat bounded cases and check conditioning, time, allocations and cancellation before any production change.
5. **Build a broader held-out material/rank dataset before relaxing admission.** Cover weak loss, high contrast, coatings and multiple regions across sizes and frequencies; compare operator and inverse requirements separately. The present 3 GHz high-contrast refusal is worth studying, but the observations do not justify reducing safety allowances globally.
6. **Keep deeper iterative or disk-backed factor research offline.** Require accurate solutions and competitive end-to-end time, not only smaller factor payloads. Extend lifecycle testing to long large-geometry sweeps and cancellation inside allocation/build loops when a production change makes that necessary.

These are ranked follow-ups from the completed study scope, not production modifications delivered by this package.

## Reproduction and evidence

All **45 planned experiments** have recorded terminal outcomes: 36 passed, six were rejected, two hit the time guard, and one completed its prototype comparison with all six alternatives failing. A passed analytical/lifecycle experiment can contain multiple solves; these case counts are not a count of individual solves. The seven regression modules complete with **101 tests and 10 subtests passed** in 58.15 s. The suite includes acceptance/resonance, adaptive polynomial, large-geometry follow-ups, resource recovery, worker-process loss and moment-cache coverage.

[Verification](verification.json) checks case completeness, preserved failures, successful certification metadata, analytical limits, lifecycle cleanup, audit-script syntax, report links and the 13 previously changed production/test file hashes against the published snapshot. A repository status/diff check at study completion also found no tracked modifications. [Regression details](validation_summary.json), [numerical summary](summary.json) and [raw-evidence hashes](evidence_hashes.json) are saved alongside this report. This package contains audit artifacts only; production code is unchanged.

[study.py](study.py) owns the isolated runner and initial capacity plan. [validation_study.py](validation_study.py) contains analytical/lifecycle checks. [comparison_plan.json](comparison_plan.json), [validation_plan.json](validation_plan.json) and [research_plan.json](research_plan.json) specify subsequent runs, dispatched serially by [run_remaining.py](run_remaining.py). [capacity_prototype.py](capacity_prototype.py) holds the experimental local/coarse preconditioners. [summarize.py](summarize.py) extracts comparisons without counting stopped/rejected runs as successes. See [environment.json](environment.json) for versions and host context, and `runs/` for requests, logs, result metadata, fields and monitors.
