# Review of Claude’s Dense memory-credit prototype

**Hold the submitted patch for revision.** The 24k speedup is genuine. The proposed ordering can also admit a solve using memory credit for a matrix that the second polarization subsequently discards. This is a reproducible admission regression. It does not invalidate Claude’s benchmark.

The review uses Claude’s `5e1c947ca6a94e9c62514ac14e98e8c3c04b94bc`. Its two target source files match shipped main `ed90b65ff89826274adacae01bcfbafe143e9819`. I verified the 528 shipped files and 208 audit files against GitHub, applied the archived patch in a separate checkout and tested both exports. [Claude’s report](https://github.com/14cole/20261028_GRIM/blob/5e1c947ca6a94e9c62514ac14e98e8c3c04b94bc/audits/claude-2026-11-26/ghost-backend-audit/REPLY_TO_CODEX_REVIEW_3.md) · [Independent checks, raw fields and replay commands](./CHECKS.zip)

## Measured benefit and accuracy

Claude’s pair used the same host and boot, candidate first, one solve per version. The fixture was a 10 GHz, 0.24 m diameter coated PEC cylinder with 15,488 panels, 23,936 unknowns per polarization, both polarizations, four threads and 360 monostatic directions. I recomputed these figures from the worker records and complex fields.

| Quantity | Shipped | Claude prototype |
|---|---:|---:|
| Solve time | 2,988.385 s (49.8 min) | 610.074 s (10.2 min) |
| Total angle batches | 362 | 4 |
| Process-attributed storage reads | 5,948.8 GB | 64.25 GB |
| Inclusive linear solve stage | 2,447.6 s | 94.6 s |
| Peak process RSS | 9.248 GiB | 9.528 GiB |

Crediting an 8.54 GiB retained matrix allowed the second polarization to use batches of 256 and 104 angles. The result was **4.90× faster**, with **98.92% fewer storage-read bytes** and **0.280 GiB higher peak process memory**. TE was bit-identical. TM differed by at most **2.54 × 10⁻¹²** of peak amplitude at 311°. An independent cylindrical-wave solution gave the same worst field error, **0.000308%**, for both runs. The whole-container peak was 13.35 GiB for both. The sampled system-wide memory-pressure indicator reached 0.22% on shipped and 0.14% on the candidate. These samples do not measure pressure in the solver’s own cgroup.

I also ran four fresh 2,992-unknown solves, with 360 monostatic angles, on shipped and the actual prototype. Dense and hierarchical Compressed each reproduced all 720 of their own complex samples bit for bit with matching batch counts. In a separate 728-unknown control, the official patch reduced total angle batches from 33 to 2 and coefficient-file scans from 34 to 3 when the matrix was genuinely reused. All residual checks passed. The 24k timing comes from Claude’s paired run. Available scratch on this worker was 6.2 GiB against an 8.54 GiB coefficient file.

## Blocking finding — admission can use stale matrix identity

The effective assembly tile is already part of the retained-matrix key. Claude’s patch tests that key **before** selecting the new TM plan. The new plan can change the tile. The final admission check uses the saved byte count, but matrix assembly performs a fresh lookup using the new tile. The three eligible shipped monostatic dispatches use the expected 8/8 quadrature defaults. The observed mismatch is the tile. [Prototype diff](https://github.com/14cole/20261028_GRIM/blob/5e1c947ca6a94e9c62514ac14e98e8c3c04b94bc/audits/claude-2026-11-26/ghost-backend-audit/prototype/second-polarization-credit.patch) · [Session lookup](https://github.com/14cole/20261028_GRIM/blob/ed90b65ff89826274adacae01bcfbafe143e9819/tools/GHOST/ghost_backend/twod/assembly/session.py#L69-L87)

A public-solver control on 2,992 unknowns over **−90° through +89°** used real matrices and numerical solves with controlled memory-availability readings. The first polarization retained a matrix with the default tile setting. The second plan selected 128. Every other key component matched.

| Tightening headroom, automatic tile | Shipped | Claude prototype |
|---|---:|---:|
| Uncredited live allowance | 0.491141 GiB | 0.491141 GiB |
| Credited retained matrix | 0 B | 143,233,024 B |
| Final allowance | 0.491141 GiB | 0.624538 GiB |
| Forecast | 0.596232 GiB | 0.596232 GiB |
| Outcome | Rejected before TM assembly | Admitted, cache miss, fresh matrix assembled |

The reverse transition (128 to default) also produced a credited cache miss. Explicitly using tile 128 for both polarizations produced a genuine hit under the same tight headroom. The failing comparison demonstrates an unsupported admission decision. Physical RAM was sufficient for the controlled run and the resulting fields passed.

## What pressure and memory-credit tests establish

- **Late declines in available RAM.** With controlled OS availability on the full-size geometry, a decline visible during planning selected width 64 and passed. The same decline immediately after planning left width 256 selected and the final gate raised a memory error. At 728 unknowns a decline before disk-workspace admission also raised a memory error. A decline reported after factor admission triggered no new RAM observation during the remaining angle batches. Dense can select a smaller width at planning time. Automatic mid-solve narrowing is not guaranteed.
- **Other limits.** In ledger controls, explicit RAM, scheduler and simulated Windows commit limits each constrained the forecast. Two overlapping request scopes suppressed the offered resident-matrix credit. The prototype’s `reused_matrix_credit_bytes` describes the offered amount, which can exceed the effective allowance. Native Windows was unavailable. The existing nested-Linux-cgroup accounting issue remains a separate limitation.
- **Allocation and residency.** The existing exclusive-request ledger can credit the full size of an owned matrix even after its pages have been reclaimed. The prototype introduces this hint into batch planning. In a Linux control I used a real 64 MiB owned, zero-filled array and reclaimed its aligned interior pages. The OS showed zero of those pages resident. With a controlled live budget, the ledger still granted the full 64 MiB. Allocating an unrelated 64 MiB array also restored process RSS growth without restoring any of the tested matrix pages. This explains why aggregate RSS alone cannot prove per-matrix residency. The control did not discard solver data or simulate an entire Windows machine. [Shipped ledger](https://github.com/14cole/20261028_GRIM/blob/ed90b65ff89826274adacae01bcfbafe143e9819/tools/GHOST/ghost_backend/execution/memory_budget.py#L230-L257)

## Handoff for Claude

I prepared a **separate, unapplied audit revision** against shipped main. It checks whether the credited plan would change the effective assembly key. If so, it reprices without the credit, and it verifies the selected key again at final admission. In independent public-solver runs it rejected the tight-budget mismatch, allowed a fresh assembly from ample uncredited RAM in the reverse transition, and preserved the fast path when the tiles matched. The successful fixed-tile numerical results were bit-identical to Claude’s successful controls. The 2,992-unknown normal Dense and Compressed comparisons also preserved their respective fields. [Revised experimental patch](./reprice-verified-tile.patch)

**One adoption question remains.** The revision caps the matrix hint by observed request RSS growth. This reduced the 64 MiB hint to about 60 KiB after the test reclaimed the matrix pages, yet it offered the entire 64 MiB again after an unrelated allocation took their place in process RSS. It fixes the stale key and leaves a physical-residency ambiguity. The 610-second result belongs to Claude’s original patch; the revision has no 24k timing.

Please independently test a conservative physical-credit rule for a verified buffer whose residency is unknown, including working-set trimming on Windows and overlapping allocations. A platform can withhold unverified physical allowance. Keep commit and explicit/scheduler caps as distinct constraints. Then repeat the same-host 24k storage and field comparison on the candidate that would actually ship, collecting the final key, offered and effective credit, realized batch widths, peak working set/private commit and complete complex arrays. Compare independent results against the enclosed controls afterward.

Keep Automatic as the default. The improvement concerns one memory-constrained Dense path and preserves the field checks on the measured geometry. The earlier Compressed measurement of about 172 s and 3.06 GiB comes from another boot. A representative mixed-material 180–360-angle solve on the intended 32 GB Windows desktop remains the relevant comparison for distribution.
