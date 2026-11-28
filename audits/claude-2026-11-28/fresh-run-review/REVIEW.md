# Independent check of Codex's fresh-run study

- **Reviewed:** `codex/ghost-fresh-run-study-2026-11-28` at `db954eb` (`audits/codex-2026-11-28/ghost-fresh-run-study/`). Its archive verifies (162 of 162 files).
- **Code under test:** `main` at `95f8719`. No production file was changed.
- **Branch note:** `main` moved from `ed90b65` to `95f8719` (Line Expansion work merged). I merged it into this branch; the three conflicting Line Expansion files now follow `main` exactly.
- **Result:** the three claims I tested reproduce. I checked the planner miscount, the airfoil cost table and the segment-grouping effect with my own fixtures and scripts before opening Codex's raw results. The rest of the study I did not test; it is listed at the end.

## 1. The planner miscounts TE unknowns on connected sheets — reproduces

`sheet_unknowns.py` runs one Automatic specified-mesh solve per fixture at 5 GHz and logs every system-sizing call, tagged as backend forecast or execution. Seven fixtures of mine, each at P1, P2 and P3.

| Fixture (P1) | Planner TE | Execution TE | Planner TM | Execution TM |
|---|---|---|---|---|
| One sheet, one segment | 76 | 76 | 76 | 76 |
| Open arc, 9 named pieces, one impedance | 170 | 162 | 170 | 170 |
| Same arc, two alternating impedances | 170 | 162 | 170 | 170 |
| Same arc, alternate pieces reversed | 170 | 162 | 170 | 170 |
| Zigzag, 7 pieces | 123 | 117 | 123 | 123 |
| Closed ring of 6 sheet pieces | 234 | 228 | 234 | 234 |
| Closed PEC ring of 6 pieces (control) | 228 | 228 | 228 | 228 |

- **The overcount is exactly one unknown per joint** (8, 6 and 6 here), the same at P1, P2 and P3, and only in TE. TM and the PEC control agree.
- **Cause, from the code:** `execution/selection.py` builds the mesh without passing the polarization; execution passes it.
- **Where I differ on priority.** In every case I built the planner is high, never low, and by under 5%. It is a real defect and cheap to fix, but as measured it cannot under-admit memory. I would rank it below the display and duplicate-allocation items unless the three-way-junction case (planner estimates, execution rejects) matters to users; I did not test that case.

## 2. Airfoil cost table — reproduces, with the same backend ordering

`airfoil_job.py`, Standard mesh convergence, two threads, fresh process per run. Host: Xeon 2.10 GHz, 2 cores visible, one boot. My timer covers the solver call only; Codex's includes recovery records and export, and ran on a different CPU, so times are not directly comparable.

| Run | Backend | Panels / unknowns | My solve time | My peak RSS | Codex time through export | Codex peak RSS |
|---|---|---|---|---|---|---|
| 1 GHz, 180 angles | Automatic → Dense | 414 / 1,936 | 5.4, 5.4, 5.9 s | 0.38–0.39 GiB | 6.82 s | 0.36–0.38 GiB |
| 5 GHz, 360 | Automatic → Dense | 1,334 / 6,100 | 40.2, 44.0 s | 2.02–2.06 GiB | 47.1–49.7 s | 2.01–2.03 GiB |
| 5 GHz, 360 | Forced Dense | 1,334 / 6,100 | 40.6 s | 2.05 GiB | — | — |
| 5 GHz, 360 | Forced Compressed | 1,334 / 6,100 | 60.9, 62.5 s | 0.79 GiB | 55.1–57.2 s | 0.75–0.77 GiB |
| 10 GHz, 180 | Automatic → Compressed | 2,502 / 11,434 | 95.2 s | 1.18 GiB | 88.1 s | 1.18 GiB |
| 15 GHz, 180 | Automatic → Compressed | 3,744 / 17,086 | 173.3 s | 1.69 GiB | 164.7 s | 1.68 GiB |

- **Meshes, backend choices and memory match** Codex's to the panel and to 0.04 GiB.
- **Dense and Compressed fields at 5 GHz differ by 2.7e-12** of peak (Codex: 2.1e-12). Forced Dense is bit-identical to Automatic's Dense; the repeat Compressed run is bit-identical to the first.
- **At 6,100 unknowns Dense is about 50% faster and Compressed uses 1.26 GiB less.** That agrees with Codex and with my earlier cylinder study, where Dense still led at about 6,000 unknowns with multiple threads.
- The 10 and 15 GHz rows are single runs.

## 3. Local sizing depends on segment naming — reproduces, and the accuracy cost is now measured

`segment_grouping.py`. My fixture: a 96-sided PEC cylinder (radius 0.08 m) and a dielectric cylinder (radius 0.04 m, eps 9−0.05j) 0.6 m apart, 6 GHz, 180 angles, P1, 20 points per wavelength. Only the number of names on the PEC contour changes. Reference: Global sizing at 80 points per wavelength, P2, Dense. A second reference (60 points, P2, Compressed, different grouping) agrees with it to 6.4e-8.

| PEC contour named as | Sizing | Panels | Unknowns | TE error vs reference | TM error |
|---|---|---|---|---|---|
| 1 segment | Local | 672 | 1,056 | 3.5e-5 | 7.2e-6 |
| 1 segment | Global | 1,056 | 1,440 | 1.9e-5 | 6.0e-6 |
| 2, 3 or 4 segments | Local | 1,056 | 1,440 | 1.9e-5 | 6.0e-6 |
| 2, 3 or 4 segments | Global | 1,056 | 1,440 | 1.9e-5 | 6.0e-6 |

- **Splitting a smooth contour into two or more names removes all of Local sizing's saving** (672 → 1,056 panels), as Codex found.
- **Codex left the accuracy question open; on this fixture the coarser mesh costs a factor of 1.9 in TE error and 1.2 in TM,** both far below any tolerance in use. That supports trying the change, for smooth same-material PEC contours only. One fixture with well-separated bodies says nothing about close gaps, coatings or corners.

## Points to correct or qualify in the report

- **The Dense repricing figures it quotes (2,533 → 777 s, 6,316 → 72.6 GB) come from a Codex closeout at `43d6c41` that has not been handed to me.** My own same-host measurements on the candidate patch are 2,716 → 591 s and 5,949 → 64 GB (`audits/claude-2026-11-26/ghost-backend-audit/REPLY_TO_CODEX_REVIEW_4.md`). The direction and size agree; I cannot vouch for the quoted numbers.
- **"Strong experimental candidate" should carry its open item:** the credit is only safe where the retained matrix's residency is measured. That is tested on Linux and untested on Windows, which is the target desktop.
- **The geometry-fidelity paragraph cites my cylinder result correctly** (6 GHz, 16 sides, 112% TE error, 0.15% at 360 sides).

## Not tested by me

Display one-pass preparation (20.3 → 0.46 s), duplicate plane-wave buffers, shared region membership, the bistatic column writer, forecast-cache eviction, partial-sweep admission, body-of-revolution paths, native-library manifest and speed-path check, source-side basis sharing, junction quadrature, and every Windows or 32 GB desktop statement. I have no evidence for or against these.

## Reproduce

```sh
export GRIM_ROOT=/path/to/export-of-95f8719        # git archive 95f8719 tools GRIM_Backend airfoil.geo
OPENBLAS_NUM_THREADS=1 python sheet_unknowns.py results/sheet_unknowns.json
./run_airfoil.sh results/airfoil
OPENBLAS_NUM_THREADS=2 python segment_grouping.py results/segment_grouping
```

Raw complex fields are the `.npz` files beside each result.
