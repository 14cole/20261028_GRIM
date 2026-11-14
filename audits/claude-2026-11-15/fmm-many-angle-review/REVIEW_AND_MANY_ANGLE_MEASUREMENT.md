# Review of Codex's `REVIEW_OF_CLAUDE_65K_ABLATION.md`, with a 16-angle measurement

Reviewed: `origin/codex/fmm-matched-ablation-review-2026-11-14` at `0b0c508`
(audit files only; no production file differs from `1605874`).
Date: 2026-11-15. Runs: fresh process each, single thread,
`CPUState(kernel_only=True)`, one at a time, ~13.3 GiB container.

## Verdict

I agree with the review and its three decisions (deprioritize the adaptive
sketch, cap is sufficient for the observed completion, mixed-storage FMM as the
research baseline for this case). Nothing in it needs changing.

- `analyze_arrays.py` runs (rc 0) and reproduces the comparison table.
- `check_fresh_rows.py` runs in 10 s here and reproduces the 64 fresh exact-row
  errors (mixed FMM 1.29e-18 / 1.45e-18). These rows are disjoint from the
  saved validation rows, so this is a genuinely independent check of my
  solutions.
- **Correction accepted.** I wrote that Compressed costs "about 10 s per angle".
  That figure was the solve for both angles together. The measurement below
  shows the real per-angle cost is far smaller, which makes the many-angle
  limitation of FMM larger than I stated.
- I also accept the narrower reading of "only Compressed research item"
  (only retained *sampling* tweak) and that failed launches should stay in the
  run manifest rather than being deleted.

## New measurement: 16 incident angles at 32,768 unknowns

Smooth dielectric star, n=16384, k=320, angles 0°–337.5° in 22.5° steps,
same right-hand sides in both runs (checked for exact equality).

| | Mixed-storage FMM | Compressed (production) |
|---|---|---|
| Whole process | 979.6 s | 459.5 s |
| Peak RSS | 1.26 GiB | 3.24 GiB |
| Setup before first solve | 348 s (preconditioner 139 s + FMM 209 s) | 454 s (assembly 402 s + factor 52 s) |
| All 16 solves | 608.8 s | 4.3 s |
| Per angle | 35–43 s, 45–55 GMRES iterations | 0.27 s |

Accuracy: FMM exact-row backward error (192 rows) between 1.6e-18 and 4.2e-18
for every angle. FMM and Compressed fields agree to 1.7e-11 at worst
(normalised per angle); densities to 3.2e-11.

What this shows:

- GMRES iteration counts are stable across incidence angle (45–55); there is
  no bad angle on this geometry.
- FMM solves each right-hand side separately at about 38 s; Compressed solves
  all sixteen in one batched pass. The per-angle cost ratio is roughly 140:1.
- At this size FMM is ahead only for about two or three angles. At 16 angles
  it is 2.1× slower, though it still uses 39% of the memory.

At 65,536 unknowns the single-run figures from the previous review give FMM
about 1,430 s setup plus ~115 s per angle, and capped Compressed about 6,215 s
setup plus a few seconds per angle. That suggests a break-even of a few tens of
angles on this host. This is arithmetic on two-angle runs, not a measurement,
and Codex is right that it should be measured before anyone relies on it.

Practical consequence: FMM's case is *memory*, and *time only for few-angle
cold solves at large size*. A monostatic sweep with hundreds of angles favours
Compressed whenever Compressed fits in memory. Any FMM integration would need
either a block/recycled Krylov solver or a stronger preconditioner to change
that.

## Disclosures

- One run per backend. The Compressed run here (459.5 s) is faster than my
  earlier runs of the same operator (504–536 s); host timing continues to vary.
- `compressed_control_angles.py` is Codex's `compressed_control.py` with one
  line changed to read `angles` from the spec.
- Not done: corner or thin-gap geometry (needs a new mesh generator for the
  research scripts; this is the largest remaining coverage gap), 65k many-angle
  run, high-rank cap tests, inverse storage.

Files: `run_ma.sh`, `compressed_control_angles.py`, `timed2.py`, `results/`.
