# Independent audit of the shipped GHOST Dense and Compressed backends

- **Code:** `main` at `ed90b65`, run from a `git archive` export. No production file was changed.
- **Handoff:** `codex/ghost-backend-accuracy-efficiency-handoff` at `c5b9a39`.
- **Order of work:** I wrote `PLAN.md`, my reference and my fixtures, and saved all my measurements before opening Codex's `REPORT.md` or its evidence archive. The one exception is the last large Dense run, which was still executing when I opened the report; its configuration was fixed beforehand.
- **Hardware:** this Linux container: Intel Xeon 2.1 GHz, 4 cores (no SMT), 15.7 GiB RAM with a 13.35 GiB cgroup limit, no swap. Python 3.13.18, NumPy 2.4.6, SciPy 1.17.1, OpenBLAS 0.3.31. Details in `environment.json`.
- **Windows:** no 32 GB Windows desktop is available to this session. That question stays open; see the last section.

## Summary

| Codex's conclusion | My result |
|---|---|
| Both backends reproduce analytic cylinder fields | **Reproduces.** My own series matches Codex's reference to 4e-15 and reproduces every figure in its accuracy table. My own fixtures agree |
| Dense and Compressed agree far below mesh error | **Reproduces.** At most 3.2e-11 up to 3k unknowns and 1.7e-10 up to 24k |
| Certification converges on the drawn polygon, not the intended curve | **Reproduces, and the effect is much larger than Codex's example shows.** A coarse polygon can be certified while more than 100% from the intended field |
| Dense is faster and Compressed lighter | **Reproduces at Codex's size; I disagree as general guidance.** Compressed is faster from about 6k unknowns on one thread and from about 12k on four, and at 24k it was 17 times faster here |

## 1. Accuracy

### My reference
`reference.py` is a cylindrical-wave series for a PEC cylinder, a homogeneous cylinder and a coated PEC core, both polarizations, with the monostatic translation phase. I derived the stored amplitude from GHOST's documented conventions as B = −4jP and did not fit any constant: the first solve matched in both polarizations to 3e-4. The series passes four checks that use no solver (a vacuum coating equals the bare core to 3e-16; lossless partial waves are unitary to 2e-15; lossy ones are sub-unitary; the PEC high-frequency limit is πa to 0.03%).

### My fixtures
360 angles, cylinder centre translated to (31, −17) mm, inscribed polygons with one panel per side. Error is max |B_ghost − B_ref| / max |B_ref|; the table gives the worse polarization. Dense and Compressed give the same error to the digits shown.

| Fixture | GHz | 128 sides | 256 | 512 | 1,024 |
|---|---|---|---|---|---|
| PEC, radius 50 mm | 3 | 0.128% | 0.032% | 0.0080% | 0.0020% |
| PEC, radius 50 mm | 10 | 0.42% | 0.105% | 0.026% | 0.0066% |
| Coated, 40/50 mm, ε 2.8−0.06j | 3 | 0.20% | 0.048% | 0.013% | 0.0032% |
| Coated, 40/50 mm, ε 2.8−0.06j | 10 | 0.70% | 0.157% | 0.042% | 0.011% |
| Coated, ε 4−0.5j, μ 1.5−0.3j | 6 | 0.30% | 0.078% | 0.021% | 0.0052% |
| Coated, 30/60 mm (thick) | 6 | 0.84% | 0.21% | 0.053% | 0.013% |

- **Convergence:** the error falls by a factor of 3.7 to 4.5 per doubling in every row, which is second order.
- **Dense against Compressed on the identical mesh:** at most 3.2e-11 (max norm) and 1.4e-11 (2-norm) over these 24 pairs.
- **Quality gates:** all 48 solves passed. Requesting Compressed ran `cpu_compressed` on the smaller systems and the hierarchical path `cpu_hmatrix` from about 1,000 unknowns.

### Cross-check of Codex's fields
Without running the solver, I recomputed Codex's three cylinder families with my series (`cross_check_codex.py`):

- its reference arrays match mine to 4.1e-15 in all twelve cases;
- its stored GHOST fields give, against my reference, exactly its table: 0.2424 → 0.0151%, 0.6538 → 0.0397%, 1.2883 → 0.0784% at 2 GHz and 0.1291 → 0.0301%, 0.0552 → 0.0154%, 0.2739 → 0.0682% at 15 GHz;
- its largest Dense–Compressed 2-norm difference is 1.83e-11, as reported.

I have no disagreement on accuracy.

## 2. What mesh certification establishes

Shipped Automatic workflow, standard target, automatic backend, wavelength sizing, 360 angles at 6 GHz. The same circle (radius 50 mm; coated case 40/50 mm) drawn as inscribed polygons. Every run was certified, published the fine mesh at P1, and ran Dense.

| Drawn sides | PEC: reported base-to-fine change | PEC: error vs circle | Coated: reported change | Coated: error vs circle |
|---|---|---|---|---|
| 16 | 0.009% | 22% | 0.019% | **112%** |
| 32 | 0.003% | 4.3% | 0.048% | 18.7% |
| 64 | 0.002% | 1.1% | 0.019% | 4.5% |
| 360 | 0.00001% | 0.034% | 0.002% | 0.15% |

- **The certificate describes the polygon.** The reported change, and the certificate's own "estimated published error" (at most 0.12%), say nothing about the distance to the intended curve. Codex's conclusion is right; its 96-edge example (0.65%, which I reproduce from its fields, and 0.16% at 192 vertices) understates how far a coarse drawing can go.
- **The error follows the gap between polygon and circle.** For PEC it is about 0.7 × 2kδ, where δ is the largest gap; for the coating it is three to five times that, because the coating thickness is also wrong. It falls as 1/sides².
- **Part of it is just lost area.** Scaling the polygon to the circle's area cuts the 32-side errors from 4.3% to 0.09% (PEC) and from 18.7% to 1.3% (coated). At 16 sides it helps much less (6% and 75%).
- **The record is honest; the status line is not explicit.** Each certificate carries `geometry_model: piecewise_linear_input` and `geometry_approximation_certified: false`, and the geometry cheat sheet says the check does not repair a coarse polygon. The GUI's result line says only "Mesh convergence: PASS (rms=…, max=…)" (`ui/solver.py:2011-2018`).

Guidance: treat certification as covering the discretization of what was drawn. For a curved boundary, redraw it with twice as many sides and compare; that test is what detects faceting error.

## 3. Time and peak memory

### Method
A coated PEC cylinder (core 100 mm, outer 120 mm, ε 2.8−0.06j) at 10 GHz, sized by side count. Each job is a fresh process, both polarizations, explicit backend, RHS compression off, batch 256, residual checks on. Backends alternate order between repeats. Nothing else ran on the machine. Every run passed its quality gate, and repeats gave bit-identical fields.

### One thread

| Unknowns per system | Panels | Angles | Dense: time (s) | Dense: peak RSS | Compressed: time (s) | Compressed: peak RSS | Runs each |
|---|---|---|---|---|---|---|---|
| 2,992 | 1,936 | 180 | 12.1 (11.5–12.6) | 0.56 GiB | 17.3 (16.7–18.3) | 0.34 GiB | 3 |
| 2,992 | 1,936 | 360 | 15.6 (14.4–16.2) | 0.58 | 19.6 (18.8–21.3) | 0.38 | 3 |
| 5,984 | 3,872 | 180 | 48.6 (46.6–48.8) | 1.83 | 40.4 (39.8–41.7) | 0.65 | 3 |
| 5,984 | 3,872 | 360 | 51.5 (50.4–52.4) | 1.86 | 42.5 (42.0–44.9) | 0.71 | 3 |
| 11,968 | 7,744 | 180 | 234 | 6.73 | 88.4 | 1.33 | 1 |
| 11,968 | 7,744 | 360 | 256 (255–257) | 6.81 | 97.5 (96.9–98.1) | 1.45 | 2 |

### Four threads, 360 angles

| Unknowns per system | Dense: time (s) | Dense: peak RSS | Compressed: time (s) | Compressed: peak RSS | Runs each |
|---|---|---|---|---|---|
| 2,992 | 7.3 (7.2–7.3) | 0.59 GiB | 14.1 (13.8–14.4) | 0.42 GiB | 2 |
| 5,984 | 22.6 (20.1–23.5) | 1.87 | 31.8 (30.4–32.4) | 0.78 | 3 |
| 11,968 | 101.5 (98.3–104.7) | 6.83 | 74.7 (72.9–76.5) | 1.56 | 2 |
| 23,936 | **2,959** | 9.26 | **172** | 3.06 | 1 |

Times are medians with the range in brackets. The analytic error of these meshes is 0.019%, 0.0048%, 0.0012% and 0.0003% from smallest to largest, the same for both backends. Dense and Compressed differ by at most 1.7e-10.

### What the measurements show
- **The crossover depends on the thread count.** On one thread Compressed is faster from somewhere between 3k and 6k unknowns. On four threads Dense is still 1.4 times faster at 6k and Compressed leads only by 12k, because the dense factorization uses the extra cores better. The ranges do not overlap in any of these comparisons.
- **Compressed always uses less memory,** by 35–40% at 3k, 2.6 times at 6k and 4.4 to 4.7 times at 12k.
- **Angle count barely matters.** Going from 180 to 360 angles adds 5 to 29% for Dense and 5 to 13% for Compressed.
- **At 24k Dense is impractical on this machine.** It completed correctly in 49 minutes; a first attempt was cut off by my own 40-minute limit. Compressed took under 3 minutes. Dense's peak RSS there (9.3 GiB) is below what the 12k run predicts by n² scaling (about 27 GiB), so it must have taken a more memory-frugal and slower route under the 13 GiB limit. I did not establish which. On a machine with more RAM the 24k Dense time could be shorter.

### Where I disagree with Codex
Codex's report says its fresh ellipse and an archived coated study "both favor Dense for elapsed time".

- **At its size it is right.** I replayed its ellipse benchmark here (1,536 unknowns, one pinned core): Dense 3.3–4.2 s against Compressed 5.4–6.5 s, with the same field agreement (2.5e-12) and the same 0.027% refinement change. Compressed saved 9% of peak RSS here, 12% in Codex's run. My 3k rows agree.
- **It does not extend upward.** Fixture: coated cylinder above, 5,984 unknowns, one thread, 180 angles, three alternating runs each: Dense 46.6–48.8 s, Compressed 39.8–41.7 s. At 11,968 unknowns Compressed is 2.6 times faster on one thread and 1.36 times on four.
- **The archived 5,883-unknown figure** (Dense 35.7 s, Compressed 43.2 s, one polarization) points the other way from my 5,984-unknown result. It predates the merged hierarchical-matrix integration and is a different fixture and frequency; I did not rerun it, so I cannot say which difference accounts for it.

One small numerical note: for the Dense backend the 180- and 360-angle grids agree on their shared angles to 1.3e-13 in my replay, not the 6.6e-15 Codex quotes; 3.4e-15 to 8.5e-15 is what Compressed gives. Both are negligible.

## Backend and mesh guidance supported by this evidence

1. **Accuracy does not decide the backend.** The two agree to 1e-10 or better at every size tested. The mesh and the drawn geometry decide accuracy.
2. **Below about 5,000 unknowns per system use Dense.** It is 1.3 to 2 times faster and memory is under 2 GiB either way.
3. **Above about 12,000 use Compressed.** It is faster at any thread count tested and uses a quarter of the memory or less.
4. **Between the two it depends on cores.** With one or two threads Compressed is already ahead at 6k; with four or more Dense still is. The shipped Automatic policy switches at 10,000 forecast unknowns, which sits inside the measured four-thread crossover and is a reasonable default for a multi-core desktop.
5. **Do not buy accuracy with unknowns you do not need.** On this fixture 3k unknowns already gives 0.02%. The sizes where Compressed wins correspond to larger bodies or higher frequencies, not to finer meshes of small ones.
6. **Draw curved boundaries finely.** At 6 GHz on a 50 mm radius, 64 sides leaves 1% (PEC) to 4.5% (coated) and 360 sides 0.03% to 0.15%, regardless of what the certificate reports. The error scales with frequency × radius / sides².

## The 32 GB Windows desktop

Not measured. What the Linux data support, for this fixture only:

- **Compressed** used about 0.13 GiB per 1,000 unknowns from 3k to 24k (3.1 GiB at 24k, 172 s on four cores for 360 angles). Memory is nowhere near a 32 GB limit at these sizes.
- **Dense** used 6.8 GiB at 12k. If that scaling continued it would need about 27 GiB at 24k, which is at the edge of a 32 GB machine; here it ran in 9.3 GiB and took 49 minutes.

These are peak RSS on Linux. Windows working set and private commit, a different BLAS and a different core count can all move the numbers.

**Highest-value remaining test:** on the actual desktop, one representative mixed PEC/dielectric model at its highest frequency, 360 angles, run once with Dense and once with Compressed at the desktop's normal thread count, recording unknowns per system, wall time, peak working set and peak private commit, and the complex fields. If the model is above about 10k unknowns, add the same run at half and double the unknowns to locate the crossover on that hardware.

## Limits of this audit

- One geometry family for timing (a coated circular cylinder). Hierarchical compression depends on geometry; a body with many close surfaces or junctions may compress less well.
- Rows marked one run have no spread. Others have two or three.
- All timing is at 10 GHz. Accuracy covers 3 to 10 GHz in my fixtures and 2 and 15 GHz through Codex's fields.
- RHS compression was off and angle batch 256 throughout, as the handoff specified. The Automatic profile's own choices were exercised only in the certification study.
- I replayed Codex's timing benchmark and recomputed its accuracy and certification results from its stored fields. I did not rerun its cylinder or certification solves.

## Files

| Path | Contents |
|---|---|
| `PLAN.md` | the plan written before measuring |
| `reference.py` | analytic series and its self-checks |
| `harness.py` | geometry builders and solve wrappers |
| `study_a_accuracy.py`, `results/a/` | 48 fixed-mesh solves; one `.npz` per solve with GHOST and analytic complex fields |
| `study_b_certification.py`, `results/b/` | 12 Automatic runs; fields, full metadata and the policy used |
| `timed_job.py`, `study_c_timing.py`, `results/c*/` | timing jobs; `runs.jsonl` per batch and complex fields for every run |
| `results/c_large/` | the 24k pair, with the Dense run's 30-second memory samples |
| `cross_check_codex.py`, `results/cross_check_codex.json` | Codex's fields against my series |
| `results/codex_bench_replay_summary.json` | Codex's ellipse benchmark replayed here |
| `summarize.py`, `results/summary.json` | all tables above |
| `environment.json` | hardware and software |

To reproduce, export `ed90b65` and from this folder:

```bash
export GRIM_ROOT=/path/to/export-of-ed90b65 PYTHONPATH=.
python reference.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python study_a_accuracy.py results/a
python study_b_certification.py results/b
python study_c_timing.py results/c 1056:180:1:3 1056:360:1:3 2112:180:1:3 2112:360:1:3 4224:360:1:2
python study_c_timing.py results/c4 1056:360:4:2 2112:360:4:3 4224:360:4:2
python timed_job.py 8448 compressed 360 4 results/c_large/compressed.npz
python cross_check_codex.py /path/to/extracted-codex-evidence
python summarize.py results
```
