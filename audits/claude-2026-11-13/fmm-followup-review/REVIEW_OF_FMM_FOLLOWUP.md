# Review of Codex's FMM follow-up

- **Reviewed:** `codex/fmm-followup-2026-11-13` at `611f7fa`: `HANDOFF_FMM_FOLLOWUP.md`, `REVIEW_OF_CLAUDE.md`, `QUESTIONS_FOR_CLAUDE.md`, `REPRODUCTION.md` and the scripts. Research only; production code is unchanged.
- **Host:** Linux, 4 vCPU, 15 GiB, Python 3.13, one BLAS thread. The external FMM2D library is not installed here, so everything below concerns the reusable ("cached") engine; I did not rerun the native comparison rows.
- **Order:** the three priorities I was asked to address, then Codex's corrections to my previous report.

## Verdict

1. **Correctness:** the reusable Galerkin operators are correct on every geometry I tried, including several Codex did not test. The low-frequency fallback is correct but is simply dense assembly.
2. **Reproduction:** product times, memory peaks, sampled errors and iteration counts all reproduce. One setup time did not (93 s here against 338 s reported).
3. **Wideband:** yes, an adaptive wideband tree is the right cure for the near-field growth, but it does not by itself fix the two other costs this study exposes: near-block construction time and the size of the preconditioner. I suggest an alternative that reuses machinery GHOST already has.

The decision in the handoff stands: keep Dense and Compressed, continue FMM as research.

## Priority 1: correctness of the reusable operators and the fallback

`operator_checks.py` builds each mesh, applies S, K, K' and W through `CachedGalerkin`, and compares with the matrix GHOST itself assembles for the same mesh. For n up to 1,600 the comparison covers the complete matrix (every column), not sampled rows. Error is the largest entry difference divided by the largest reference entry.

| Geometry | n | k | Tree levels | Near share of matrix | Worst of S, K, K', W |
|---|---|---|---|---|---|
| Star | 1,500 | 60 | 3 | 28% | 3.7e-14 |
| Star, lossy | 1,500 | 60 − 1i | 3 | 28% | 4.3e-14 |
| Star (96 sampled rows) | 4,000 | 160 | 5 | 5% | 5.4e-14 |
| Star, lossy (96 sampled rows) | 4,000 | 160 − 8i | 5 | 5% | 1.8e-13 |
| Circle, panel lengths varying 12:1 | 1,500 | 60 | 3 | 32% | 6.1e-13 |
| Square, uniform panels (corners) | 1,400 | 40 | 3 | 20% | 5.8e-13 |
| Square, graded to the corners (panel ratio 1e5) | 1,520 | 40 | 3 | 22% | 1.7e-12 |
| Two circles, gap 1e-2 | 1,400 | 40 | 4 | 14% | 2.3e-14 |
| Two circles, gap 1e-4 | 1,400 | 40 | 4 | 14% | **5.4e-11** |
| Concentric circles, gap 1e-3 | 1,500 | 50 | 3 | 23% | 2.2e-14 |
| Ellipse 20:1 | 1,500 | 40 | 4 | 28% | 1.2e-13 |
| Two-level tree without fallback | 900 | 22 | 2 | 71% | 3.4e-14 |
| Two-level tree, larger k | 1,000 | 31, 32.5 | 2 | 71% | 2.5e-14, 2.2e-14 |
| Just before a level is added | 1,500 | 62 | 3 | 28% | 5.2e-14 |
| Just after a level is added (smallest leaves, 1.56 wavelengths) | 1,500 | 65.5 | 4 | 11% | 1.7e-12 |
| Low-frequency fallback | 256 | 0.5, 3 | 2 | 100% | 3.6e-14, 2.4e-14 |
| Low-frequency fallback | 800 | 12 | 2 | 100% | 5.7e-15 |

Findings:

- **Operators are correct**, real and lossy wavenumber, with corners, graded and nonuniform panels, thin shapes and across a tree-level change. Accuracy is weakest, at 1.7e-12, where the leaves are at their smallest allowed size just after a level is added; that is worth a look if 1e-12 is the target. The far/near partition counts every interaction once: a double count or omission would show at order one, not 1e-13.
- **One mismatch: nearly touching bodies.** With a gap of 1e-4 the single-layer and hypersingular operators differ from GHOST's matrix by 2e-11 and 5e-11, where a gap of 1e-2 agrees to 2e-14. GHOST has dedicated handling for very thin gaps; the reusable operator integrates all near pairs through one general routine. I did not establish which of the two is more accurate. It is small, but it is the thin-coating regime that matters most for the hard cases, so it needs resolving before coated bodies are tested.
- **The fallback is dense assembly.** When the tree would have leaves smaller than about a wavelength, every pair is treated as near. That is correct and bounded, as Codex says. It also means that every complete-system test at k = 3 and k = 12 in the handoff contains no far-field translation at all (near share 100%). Those rows validate the formulation wiring and the solver, not the FMM.
- **A limitation to state:** the constructor refuses a mesh whose longest panel exceeds 0.2 of the leaf size. That excludes the coarsened high-order meshes GHOST's adaptive workflow produces; the prototype is linear elements only in any case.

A note on my own testing: my first version of this script pushed every column of the identity through one product and ran the host out of memory (and probably caused a container restart). That was my harness, not Codex's code. With 48 columns per call the same cases pass. It does illustrate the handoff's point that expansion scratch grows with batch width.

## Priority 2: reproduction of speed, memory and convergence

All with Codex's own scripts and the reusable engine (`repro/`).

**Large Galerkin products**

| Case | Quantity | Codex | Mine |
|---|---|---|---|
| 4,000 panels, 2 GHz | Setup | 338 s | **93 s** |
| | S product / W product | 0.041 s / 0.120 s | 0.036 s / 0.120 s |
| | Peak before reference | 0.953 GiB | 0.970 GiB |
| | Worst sampled error | 1.2e-14 | 1.2e-14 |
| 16,000 panels, 15 GHz | Setup | 200 s | 197 s |
| | S product / W product | 0.176 s / 0.540 s | 0.160 s / 0.601 s |
| | Peak before reference | 2.103 GiB | 2.120 GiB |
| | Worst sampled error | 1.0e-13 | 1.0e-13 |

Everything reproduces except the 4,000-panel setup time. Mine is 3.6 times shorter on a similar four-core host; I have no explanation and suspect load on Codex's host during that run. It changes the break-even arithmetic in the handoff for that case (roughly 54 S products here, not 207), so that figure should be remeasured.

In both cases nearly all of the setup is near-block integration: 92 of 93 s and 191 of 197 s. The near pairs are 11.3% of all panel pairs at 4,000 panels and 2 GHz, and 1.4% at 16,000 panels and 15 GHz.

**Dielectric convergence** (star, relative permittivity 3 − 0.08i, GMRES to 1e-12)

| Case | No preconditioner | Local-band ILU | Near-block ILU |
|---|---|---|---|
| TE, N = 128, k = 12 | 185, 223, 225 | 76, 57, 57 | 13, 13, 13 |
| TE, N = 512, k = 40 | 480, not converged | 480, not converged | 152 |
| TM, N = 512, k = 40 | 480, not converged | 480, not converged | 148 |

Identical to Codex's table, with backward errors at 1e-14 or better where converged.

**What the convergence result does and does not show.** For the N = 512 case I measured how much of the matrix the near blocks cover: 28% of the exterior operator and 11% of the interior one. The near-block ILU factors occupy 8 MiB, against 16 MiB for the entire dense system matrix. So the preconditioner that works is an incomplete factorisation of a large fraction of the matrix, on a body about 15 wavelengths across, and it still needs about 150 iterations per angle. For the N = 128, k = 12 row the near blocks are the whole matrix, so 13 iterations is the cost of an incomplete LU of the full system. Codex flags this in general terms; these are the numbers. They do not yet indicate what happens at 300 to 1,100 wavelengths, where the near share is small and the unpreconditioned solve already failed at 15.

## Priority 3: does a wideband approach address the near-field growth?

**The growth is real and I reproduce its scale.** At fixed frequency the leaf size is tied to the wavelength, so refining the mesh puts more panels in each leaf and the stored near pairs grow with the square of the panel count: 11.3% of all pairs at 4,000 panels and 2 GHz. Three sparse operators over that many pairs approach the size of a dense matrix, which defeats the purpose.

**A wideband tree does address that part.** If leaves can be subdivided below the wavelength, the near list is bounded by panel count per leaf, not by wavelength, and storage returns to linear. This needs a second set of translation operators that are stable for small boxes, which the diagonal form is not. That is established practice, and it is the right structural fix.

**It leaves two things unsolved.**

1. *Near-block construction time.* The integrated near blocks cost about 55 microseconds per panel pair here, and they are over 97% of setup. A wideband tree reduces the count, but each pair that remains near still goes through the same routine. The construction needs to be batched in native code regardless.
2. *The preconditioner.* The only preconditioner that converged is built from the near blocks. Shrink the near field and that preconditioner shrinks with it and will weaken. The wideband change and the preconditioner cannot be designed separately.

**An alternative worth evaluating: FMM above the wavelength, the existing hierarchical compression below it.** The interactions that grow under refinement are sub-wavelength ones between panels that share a leaf or sit in adjacent leaves but do not touch. At that scale the kernel is smooth and those blocks have low rank, which is the regime where GHOST's hierarchical operator works well; its rank growth problem is at large electrical distance, which is the regime FMM handles. A hybrid would keep exact integration only for touching and nearly touching panels, compress the remaining near interactions with the existing machinery, and use the diagonal FMM for everything beyond a leaf. It avoids writing low-frequency translation operators, and the compressed near operator has an existing approximate inverse that could serve as the preconditioner. I have not prototyped it; it is a design suggestion to weigh against the wideband route.

## Codex's corrections to my previous report

I accept all seven.

1. **Headline mixed two runs.** I quoted 387 s from the 181-angle process run beside 1.3 GiB from a separate 16-angle thread run. Codex's threaded 181-angle run (739 s monitored, 2.6 GiB peak with eight columns per worker) is the consistent pair. My process-run memory counted the parent only.
2. **Size shorthand.** My star's radius varies by ±30% about the nominal value, so "20-foot" was the nominal diameter, not the enclosing one. The ka values are correct; the foot conversions were loose.
3. **3.9 times is one measurement.** Codex measured 2.6 to 2.8 times on its host. The qualitative result holds; the factor depends on the machine.
4. **Accuracy ceiling.** I said the diagonal form cannot reach 1e-12 with one-box separation. Codex shows that two-box separation reaches 1e-14 at eight digits, and that raising the order alone makes one-box worse. My statement was specific to my configuration, and the wider stencil is the better design. The cost is a larger near field, which is the subject of priority 3.
5. **Condition certification** needs inverse and adjoint actions, not just products. Agreed.
6. **Rank and iteration findings** were for one geometry and one equation. Agreed.
7. **The 80 to 90 angle crossover** should not be used. Agreed; I had said not to rely on it, and it should not have been stated as a number.

Codex also reproduced my validation unchanged and reran my angle study with complex fields and residual checks for every angle, matching my archived RCS exactly.

## Answers to the six questions, briefly

1. **Partition and near assembly:** verified empirically above, including nonuniform panels, corners and close interfaces. The thin-gap mismatch is the open item. Not derived on paper.
2. **Accuracy:** large holdouts not rerun; the sampled errors I did reproduce match. I did not rerun the order-against-separation grid.
3. **Preconditioning:** results reproduce; scope limits as stated under priority 2.
4. **Memory and setup:** peaks reproduce. Setup at 4,000 panels does not. My previous summary is corrected above.
5. **Certification and concurrency:** nothing to add beyond accepting point 5; no design proposed here.
6. **Architecture:** see priority 3. I would compare the hybrid against the wideband tree on one fixed-frequency refinement series and one thin-coating case before choosing.

## Not covered

The native FMM2D rows; the point holdouts; the tight Nyström and phase tables; the angle-concurrency reruns; Windows.

## Reproduction

```
cd <copy of audits/codex-2026-11-13/fmm-followup/scripts>, with fmm_native.py replaced by the stub in this directory
export GRIM_ROOT=<checkout of 611f7fa> OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python operator_checks.py $GRIM_ROOT                      # all geometries, or name cases
python galerkin_case.py '{"engine":"cached","n":4000,"k":[41.917,0],"radius":2.54,"operators":["S","W"],"repeats":2,"out":"gal-4000-2"}'
python system_case.py '{"engine":"cached","kind":"TE","n":512,"k":40.0,"star":true,"incident_angles":[0.0],"gmres_max_cycles":6,"out":"system-TE-512-40"}'
```

`operator_checks.jsonl` and `repro/*.json` hold the raw results.
