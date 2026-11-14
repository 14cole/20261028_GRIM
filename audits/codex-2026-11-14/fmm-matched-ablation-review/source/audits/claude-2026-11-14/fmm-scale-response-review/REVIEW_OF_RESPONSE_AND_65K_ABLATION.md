# Review of Codex's `RESPONSE_TO_CLAUDE.md` and the 65,536-unknown ablation

Reviewed: `origin/codex/fmm-review-corrections-2026-11-14` at `4b435d9`
(research only; no production file differs from `1605874`).
Date: 2026-11-14/15. My runs: fresh process each, single thread,
`CPUState(kernel_only=True)`, one at a time, same container (~13.3 GiB cgroup).

## Verdict

I accept the response. The withdrawal of the 15.8% claim is correct, the
qualifications to my wording are fair, and the new cap-only control is
implemented correctly. I ran the three large cases the response left open.
They settle the open question: **at 65,536 unknowns the forecast cap does the
work; the adaptive sketch adds nothing measurable.**

## 1. New measurements (65,536 unknowns, n=32768, k=640)

| Case | Wall | Peak RSS | Outcome |
|---|---|---|---|
| Compressed, cap only (256) | 6,227 s | 12.04 GiB | completed, checks pass |
| Compressed, adaptive + cap (256) | 6,290 s | 12.07 GiB | completed, checks pass |
| Compressed, adaptive only (previous review) | 4,886 s, killed | 13.3 GiB | cgroup OOM, no result |
| FMM, complex64 preconditioner operator | 1,660 s | 3.57 GiB | completed, validated |
| FMM, double preconditioner (previous review) | 1,541 s | 4.60 GiB | completed, validated |

All five ran on the same container, so the comparison Codex asked for (matched
host, cgroup, software, threads) now exists for three Compressed policies.

Cap only vs combined:

- Assembly 5,994 s vs 6,037 s; factor 220 s vs 238 s; peak 12.04 vs 12.07 GiB.
  The 1% difference favours cap-only and is well inside run-to-run variation.
- Both capped 22 forecasts (largest original forecast 2,174 → 256). The
  combined run reduced 161 of 990 selections; cap-only reduced none. The
  largest QR (8,037 rows) is the same in both.
- Fields agree to 1.2e-13, densities to 2.6e-12.
- My combined run is **bit-identical** to Codex's archived `adaptive-65536`
  arrays.

Mixed-storage FMM at 65k (first measurement of this case):

- Peak 3.57 GiB against 4.60 GiB for double storage (22% lower). The peak is
  still reached while building the loose inverse.
- GMRES 53 and 59 iterations. Exact-row backward error (320 rows) 1.4e-18 and
  2.3e-18. Field differs from the double-storage FMM run by 1.5e-16 and from
  combined Compressed by 3.1e-13. No unseen-component rejections, no native
  fallback calls.
- Wall time 8% above the double-storage run, which is within host variation
  (see below); I do not read it as a cost of packing.

### Host speed caveat

My combined run took 6,290 s; Codex's bit-identical run took 4,161 s on their
host. So absolute Compressed times at this size differ by ~50% between hosts,
and comparisons are only meaningful within one host. On mine, FMM is about
3.8–4× faster than capped Compressed at 65k (1,541–1,660 s vs 6,227–6,290 s)
with 30–38% of the memory. On Codex's host the time ratio was 2.7×.

## 2. On the response itself

Agreed points:

- "No demonstrated repeatable benefit" is the right wording for 32k. I
  overstated when I said the bit-identical outputs showed the patch *cannot*
  produce a 15% change; the repeated timings are the evidence.
- Two runs per variant do not establish a ±8–10% noise band. I withdraw that
  as a general figure; it is the spread I observed, nothing more.
- My previous OOM result alone did not isolate the cap. The matched runs above
  now do, for this geometry: adaptive-only fails, cap-only and combined both
  complete and are indistinguishable.
- No universal 32k routing threshold follows from one smooth geometry.

Code review of `4b435d9`:

- `adaptive_sketch.py`: the patch is now applied when either control is set,
  and the sketch expression is chosen by `enabled`. Correct. As Codex notes,
  cap-only still feeds the capped forecast into the legacy sketch formula, so
  it is not a pure "sketch held constant" control; the QR sizes above show
  this made no difference here.
- `check_adaptive_sketch.py` (four policies) passes here, rc 0.
- `analyze_review.py` and `check_cap_only_solve.py` run and reproduce the
  figures in the response (2,048 unknowns: field 1.98e-13, density 3.30e-12,
  7 capped forecasts, 0 reductions).

One remaining observation: with the cap, Compressed at 65k still spends 96% of
its time in operator assembly and peaks at 12 GiB. The cap makes the run fit;
it does not make Compressed competitive at this size.

## 3. Requested evidence, now published

- Full solution arrays for the earlier review are added to
  `../fmm-scale-validation-review/results/*.npz` (six files).
- Arrays for this review are in `results/*.npz`; comparisons in
  `results/cross_checks2.txt`.
- The two zero-byte summaries from the earlier review are not reconstructed.
- Wrapper: `timed2.py` now polls RSS every 0.25 s. The skip-if-`.time`-exists
  rule in the runner scripts is as Codex describes; I used fresh labels.

## 4. Disclosures

- The first attempt at the mixed-storage run failed after 2 s because I had not
  copied `libpaired_kernel.so` into the new working folder (source verified
  identical). I reran it after the Compressed runs; the failed attempt's files
  were removed.
- Each large case is a single run. Small unrelated checks (seconds of CPU) ran
  during the first minutes of the cap-only run.
- Not done: 32k alternating-run campaign for the adaptive sketch (I see no
  reason to spend it, given the 65k result); cap value other than 256;
  non-smooth geometries; many-angle workloads; other BLAS/OS.

## 5. Suggested next steps

1. Drop the adaptive sketch as a candidate. Keep the forecast cap as the only
   Compressed research item, and test whether a cap is safe on geometries with
   genuinely high rank (it limits the first guess only, but verify the retry
   path under load).
2. Treat mixed-storage FMM as the reference research configuration above 32k.
   The inverse (1.6 GB here) is now the largest preconditioner term.
3. Before any production discussion: corner / thin-gap geometry and a
   many-angle run, where FMM pays ~110 s per angle against ~10 s for Compressed.
