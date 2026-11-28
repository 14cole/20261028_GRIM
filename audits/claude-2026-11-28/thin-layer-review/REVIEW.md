# Independent review of the thin-dielectric planning prototype

- **Reviewed:** `codex/thin-layer-planning-trial-2026-11-28` at `f1564a7`, against the release candidate `6621db2`. Cross-checked afterwards with `STUDY.md` and `REPLAY.zip` at `ecc3e1a`.
- **Method:** my own fixture and tracer (`trace_case.py`), one fresh process per solve, run on exports of both commits before I opened Codex's study. Neither branch was merged into mine.
- **Recommendation: merge,** as its own change after PR #4. On every case I ran the prototype's forecasts equal the system that is solved, every memory check prices the operator that is built, fields are unchanged, and it removes one understatement that the release candidate has. Limits are listed at the end.

## Fixture

A thin dielectric layer (0.5 mm, eps 3.2−0.02j) at 3 GHz on a polyline of six straight pieces with 1° turns, 20 panels per free-space wavelength. The same physical surface is written five ways: one named segment; three; six; "mixed" (five names, two of them reversed, listed out of order); and "many" (one name per three panels, every second one reversed, shuffled). Monostatic, 240 angles, both polarizations. Also a closed ring of eight names with three reversed, and two disconnected strips.

The tracer records each desktop forecast, each HPC forecast through the public planner in both channel orders, each solve-time memory estimate with the operator family it priced, the operator handed to the linear solver (type and shape), the right-hand-side shape, every numeric sample column, and peak process RSS.

## 1. Forecasts against the systems that produce the fields

128 panels, joined midsurface 129 nodes. Operator and right-hand-side sizes were 258 (TE) and 129 (TM) with 240 columns in every run on both trees.

| Naming | `6621db2` desktop and HPC forecast, TE / TM | `f1564a7` forecast | Operator solved |
|---|---|---|---|
| one name | 258 / 129 | 258 / 129 | 258 / 129 |
| three | 262 / 131 | 258 / 129 | 258 / 129 |
| six | 268 / 134 | 258 / 129 | 258 / 129 |
| mixed, reversed, shuffled | 266 / 133 | 258 / 129 | 258 / 129 |
| ring, 480 panels, eight names | 976 / 488 | 960 / 480 | 960 / 480 |
| two strips, four names | 440 / 220 | 436 / 218 | 436 / 218 |
| many, 608 panels, 200 names | 1,616 / 808 | 1,218 / 609 | 1,218 / 609 |

- **Desktop, HPC (both channel orders) and the first solve-time check all agree with the operator on the prototype.** On the release candidate only the thin-layer solver's own inner check does.
- **Fields:** 38 result pairs, release candidate against prototype, are bit-identical in every numeric column, including the stored residual (largest 3.8e-15). This covers Dense, Compressed and Automatic, monostatic and one bistatic case.
- **Renaming does not change the answer:** three and six names give bit-identical fields to one name; the reversed and shuffled version differs by 2.7e-16. Dense and Compressed differ by 3.0e-16.
- **Magnetic contrast** (mu 1.5−0.1j) makes TM a two-block system too: 258 / 258 on the prototype, 266 / 266 forecast on the release candidate, 258 / 258 solved. **Zero contrast** is 0 / 0 everywhere.

This also settles my earlier "not confirmed" on the thin-layer finding. My previous probe had the evidence (forecast 48 / 24, solver 42 / 21) and I misread the 42 / 21 as a qualification solve. Codex's reading was right.

## 2. Does Compressed budget for the operator it builds?

Default hierarchical cutoff 1,024 unknowns. "Mixed" naming, forced Compressed. "H" is the hierarchical operator, "S" the streamed-tile operator. Modeled peaks are the solver's estimates; measured is the whole-process high-water mark for both polarizations.

| Joined system, TE / TM | Tree | Planner priced (TM) | First solve-time check | Inner thin-layer check | Operator built (TM) | Modeled TM peak | Measured process peak |
|---|---|---|---|---|---|---|---|
| 2,046 / 1,023 | `6621db2` | H at 1,027 | H, 0.258 GiB | S, 0.327 GiB | S, 1,023 | 0.258 then 0.327 | 0.240 GiB |
| 2,046 / 1,023 | `f1564a7` | S at 1,023 | S, 0.327 | S, 0.327 | S, 1,023 | 0.327 | 0.241 |
| 2,048 / 1,024 | `6621db2` | H at 1,028 | H, 0.256 | **S, 0.327** | **H, 1,024** | 0.256 then 0.327 | 0.248 |
| 2,048 / 1,024 | `f1564a7` | H at 1,024 | H, 0.259 | H, 0.259 | H, 1,024 | 0.259 | 0.248 |

- **Below the cutoff the release candidate plans and admits a hierarchical operator and then builds a streamed one,** so its planner understates the modeled TM peak by 0.07 GiB. The prototype prices the streamed operator at every step.
- **At the cutoff the release candidate's inner check prices the wrong family** (streamed, while a hierarchical operator is built). The prototype's three checks agree with execution.
- **TE systems of 1,022, 1,024, 2,046 and 2,048 unknowns all use the streamed operator and are priced as streamed on both trees.** The hierarchical operator was selected only for the single-block (TM) system.
- **Modeled peak was above measured process memory in every solved prototype run** except the zero-contrast case, where the model says 0.064 GiB and the bare interpreter already holds 0.083 GiB. That is identical on the release candidate.
- Automatic chose Dense for all of these sizes on both trees, with the same corrected forecasts.

## 3. Changed admission decisions

"Many" fixture: 200 names over 608 panels, so the release candidate forecasts 1,616 TE unknowns and the solver assembles 1,218. Reservation set with `GHOST_MAX_SOLVE_GB`.

| Backend | Reservation | `6621db2` | `f1564a7` |
|---|---|---|---|
| Dense (needs 0.452 by the old count, 0.434 by the real one) | 0.44 GiB | refused | solved |
| Dense | 0.42 GiB | refused | refused |
| Compressed (0.361 old, 0.328 real) | 0.34 GiB | refused | solved |
| Compressed | 0.32 GiB | refused | refused |

- **Both admitted jobs are bit-identical to the prototype's ample-budget run and to the release candidate's ample-budget run,** in all 18 numeric columns.
- **The admissions are justified:** the matrix that is built is the 1,218 one, and measured peak RSS was 0.17 GiB against the 0.44 and 0.34 GiB reservations.
- **Newly rejected supported geometry: none found.** Ring, disconnected strips, reversed and shuffled names, magnetic and zero contrast, and Dense bistatic all solve on both trees with identical fields. Compressed bistatic is refused on both, with the same message.
- **Earlier rejection of an unsupported request:** an explicit P2 basis is refused at solve time on both trees. On the prototype the HPC planner also refuses it; on the release candidate the HPC planner returned a 522 / 261 forecast for a job that could not run.
- **Understated memory: none found on the prototype.** The only understatement I saw is the release candidate's, in section 2.

## Cross-check with Codex's study

- **Agreement.** Codex reports the same pattern on its own fixtures: forecasts on split names exceeding the factorized size, a reservation that straddles the estimate, and at the cutoff a hierarchical forecast for a streamed 1,023-unknown operator with the modeled peak rising from 237 to 334 MiB once corrected. I measured 264 to 335 MiB on a different geometry.
- **One thing I add.** At exactly 1,024 unknowns the release candidate's inner check prices the streamed operator while the hierarchical one is built. Codex's table describes that case as simply correct on both.
- **No disagreement,** so no reproducer is attached.

## Limits of this review

- Linux only; systems up to 2,048 unknowns; one run per case. No large solve, so nothing here speaks to desktop capacity.
- The desktop forecast is only exercised when the backend is Automatic; with a forced backend I traced the HPC planner and the solve-time checks.
- Not tested: a layer whose named pieces carry different thin-layer definitions, branching layers, curvature beyond the approximation's limit, the standalone mesh entry point (Codex says it keeps its old estimate), certified Automatic mesh search, and planning time.
- Whether the thin-layer approximation is physically accurate is a separate question that neither study addresses.

## Reproduce

```sh
git archive 6621db2 tools GRIM_Backend | tar xf - -C /path/rc
git archive f1564a7 tools GRIM_Backend | tar xf - -C /path/proto
RC=/path/rc PROTO=/path/proto ./run_all.sh
```

Each run writes its input `.geo`, a JSON trace and an `.npz` of every numeric sample column under `results/`. Host details are in `results/host.txt`.
