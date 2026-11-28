# GHOST Dense memory admission · fourth-round review

**Decision. Accept the tile-identity fix and the recorded 24k Linux speedup. Hold the candidate from distribution.** On a real two-body solve, the candidate counted 35.30 MiB of Linux shared zero pages as RAM the matrix already owned. TM had to allocate those pages when it wrote the matrix. The difference changes the solver’s admission decision near its physical-memory limit. The candidate also enables an untested Windows probe. The audit branch contains an unapplied follow-up for independent review.

The code under review is Claude’s patch at `d0b732f`, based on shipped `ed90b65`. I verified the 528 shipped file blobs and 256 blobs in Claude’s audit directory, applied the patch to an isolated export and ran the public monostatic solver. Every comparison below identifies the patch and whether the run was fresh or archived. [Claude’s fourth reply](https://github.com/14cole/20261028_GRIM/blob/d0b732fc025d47118ae999970be0f392bff9e89f/audits/claude-2026-11-26/ghost-backend-audit/REPLY_TO_CODEX_REVIEW_4.md) · [Original candidate](https://github.com/14cole/20261028_GRIM/blob/d0b732fc025d47118ae999970be0f392bff9e89f/audits/claude-2026-11-26/ghost-backend-audit/prototype/candidate-vs-ed90b65.patch)

## What the large run establishes

These are Claude’s raw one-run-per-version Linux measurements. I independently recomputed the table from the logs, compared all 720 complex outputs per version, and solved the cylinder boundary equations independently for the analytical reference. The fixture was a 0.24 m diameter lossy dielectric cylinder with a 0.20 m diameter PEC core, relative permittivity 2.8 − 0.06i, 10 GHz, 15,488 linear panels and 23,936 unknowns per polarization. It covered 0° through 359° monostatic.

| Metric | Shipped Dense | Claude candidate |
|---|---:|---:|
| Solve time | 2,716.204 s | 591.306 s |
| Peak process RSS | 9.259 GiB | 9.543 GiB |
| Peak sampled container anonymous memory | 9.116 GiB | 9.399 GiB |
| Physical storage reads | 5,948.64 GB | 64.17 GB |
| Outer right-hand-side batches across TE and TM | 362 | 4 |
| Factorizations / total right-hand sides | 2 / 720 | 2 / 720 |
| Largest reported residual | 4.57 × 10⁻¹¹ | 1.35 × 10⁻¹¹ |

Dense saved **35 minutes 25 seconds** on this pair, a **4.59× speedup**, while using **0.28 GiB more** peak RSS. The retained 8.54 GiB matrix was correctly identified at tile 128. The final gate recorded 9,166,909,440 credited bytes out of 9,166,913,536 allocated. TM went from 360 single-angle batches to 256 + 104. Factorization times were 320.0 and 315.5 seconds. The time saving came primarily from solving in wider batches and rereading less data. TE was bit-identical. TM’s largest difference divided by the peak shipped field was 2.54 × 10⁻¹². Peak-relative errors against the independent analytical solution were 3.02 × 10⁻⁶ TE and 3.08 × 10⁻⁶ TM.

The archive identifies a candidate-first pair. Uptime and counters are consistent with the recorded single boot. It contains no boot ID, has some sampled system pressure, and provides one observation per version. The earlier Compressed result of 172 s and 3.06 GiB came from another host session. **Keep Automatic as the normal backend choice.** This paired Linux cylinder result offers no measured time for a 32 GB Windows desktop, complex full-scale bodies, or a particular angle count on a different mesh.

## Findings that affect release

### 1. Linux residency can overstate the RAM already paid for

The public Dense solver reproduced the problem without forking or discarding solver pages. I used two separated PEC cylinders with distinct lossy dielectric coatings, 10 GHz, 2,880 unknowns, five monostatic angles, ordinary in-memory residual storage and a 0.7 GiB user budget. With NumPy’s huge-page advice disabled, `mincore` counted 32,399 resident 4 KiB pages at both the TM plan and final gate. Of these, 9,036 contained only zeros and were shared. When the actual TM preparation cleared the same destination, all 9,036 became exclusive and process private dirty memory rose by exactly **35.296875 MiB**. With the host’s default transparent huge-page behavior, the change on this geometry was **0.1875 MiB**. With the base-page configuration and disk residual storage, all retained pages were already private. All completed field pairs across these controls were bit-identical.

The production ledger also demonstrated the consequence. I supplied 0.48 GiB of spendable physical headroom at the two credit-bearing reads. The TM estimate was 0.586694 GiB. Claude’s gate admitted it with 0.603592 GiB. Excluding the shared pages produced a 0.569123 GiB limit and a refusal. This experiment controlled the reported headroom. The machine itself had ample RAM, and the observed outcome was a changed admission decision. A separate synthetic 64 MiB fork control showed the same principle for previously nonzero pages. Rewriting the parent increased combined proportional resident memory by about 64 MiB while `mincore` credit stayed constant. The normal GHOST workers examined here use spawn. The public two-body case establishes reachability independently of that diagnostic.

I repeated the two-body test with **180 signed monostatic angles** from −90° through +89°. With the original 0.7 GiB budget and 32-column batches, both solvers completed with bit-identical fields and the candidate again overcredited 35.30 MiB. With the same controlled 0.48 GiB physical headroom, Claude’s candidate accepted the 0.587362 GiB forecast and the integrated revision refused it. Requesting 180 columns at that same budget made both versions stop at the earlier TE factorization-copy check. At 2 GiB both completed with 180-column batches. In that paired assembly path the two probes agreed on the private pages. The angle count, batch width and available RAM determine which path a user actually reaches.

### 2. Missing credit can prevent completion, and Windows credit is enabled in the candidate

Shipped Dense passes the size of the matched retained matrix to its **final** gate even when its forecast selects one angle per batch. Claude’s candidate passes zero when the measurement fails. In a fresh 2,992-unknown, 180-monostatic-angle disk solve with controlled OS available-memory readings and the unmodified ledger, the TM estimate was 0.596232 GiB. Shipped admitted it at 0.643396 GiB and completed at width 1. The candidate with a working Linux reading completed at width 180. With the reading unavailable, the candidate’s final limit was 0.565569 GiB and it refused TM. A separate 728-unknown series reproduced this and covered failure between planning and the final gate. With ample memory a missing read still allowed completion. Users at the boundary could therefore see a RAM refusal on a previously completing mesh.

The candidate calls `QueryWorkingSetEx` on Windows and tries the POSIX probe on every other OS. Dispatch tests confirm this. The written recommendation to withhold Windows credit is absent from the code. No native Windows working-set, commit, or elapsed-time measurements were available in either fourth-round review. A conservative cross-platform policy requires a code change. Private commit and working-set residency need separate measurements. The supplied Windows script tests self-trimming, unrelated allocation, and rewriting half the original buffer. It is available in the evidence archive for native use.

### 3. One dielectric lookup can discard the priced array

A successful session lookup alone cannot prove that assembly wrote the same buffer. For an accepted but extreme homogeneous dielectric with relative permittivity 2 × 10¹² and permeability 2 × 10⁻¹², the saved scaling factor fell below the rescaling threshold. TM retrieved the priced matrix, released it and allocated a replacement. Weak-reference instrumentation showed that the old object had expired before allocation. At both 96 and 768 unknowns the allocator reused its virtual address. There was no observed duplicate allocation, excess peak or field error. Rebuilding this exceptional branch in the existing array restores the identity invariant. It preserved every tested complex field for ordinary and extreme materials.

## Verification of the previous tile finding

Across all 148 archived attempts, the first prototype had six stale-credit lookups and one changed admission at 0.46 GiB of controlled spendable TM headroom. Claude’s latest candidate and the prior Codex tile correction agreed in every one of 37 corresponding cases, including all 23 completions, 14 refusals and the complete fields of the matching successful cases. Across all 93 completed archival solves, the largest pairwise complex-field difference divided by the smaller peak was below 6.07 × 10⁻¹³.

Fresh public solves at 2,992 unknowns and 180 signed angles verified both automatic tile transitions and a pinned tile. Moving from 0 to 128 withdrew credit and refused a tight request. Moving from 128 to 0 granted zero credit, rebuilt and finished. Pinning 128 retained the priced destination and completed. Separate fresh 360-angle runs at 2,992 unknowns compared shipped with both Claude’s candidate and the integrated Codex addition through Dense and Compressed. Every before/after field was bit-identical with the same batch counts and stage-call counts.

## Unapplied follow-up for independent review

`private-matrix-reuse.patch` applies **on top of** Claude’s `candidate-vs-ed90b65.patch`. It uses Linux per-page flags for this GHOST-owned writable contiguous array, counts only whole pages reported present, exclusively mapped and anonymous, and gives zero when it cannot read or interpret that state. It also rebuilds the exceptional homogeneous-dielectric system in the matched array. The revised probe tests page-state bits and requires no physical frame numbers. It returns zero on Windows and other platforms. That withholding carries the admission consequence above. [Supplementary patch](private-matrix-reuse.patch)

- On the two-body case the integrated code withheld the 35.30 MiB and refused at 0.569123 GiB under controlled pressure. With ample headroom it completed with bit-identical fields. It retained the wide batch on the ordinary disk-backed 728-unknown control.
- A separate full-size **allocation** test filled an owned Fortran-order 23,936² complex matrix. The revised code credited all 9,166,909,440 whole-page bytes. Its single scan took 0.012 s here. The original candidate’s separate `mincore` scan of a same-size allocation took 0.191 s. These are probe observations on this kernel. The original candidate’s cited sub-0.1 s estimate is host-dependent.
- A separate 144 MiB huge-page control credited the written matrix, withdrew all credit while fork-shared, counted 284 KiB after sparse parent writes when the covering mappings had 288 KiB private dirty, and restored full interior credit after a complete rewrite. Held-zero, half-written, fork-shared, rewritten, partial-edge, view, read-only, unavailable-procfs, short-read, and unsupported-platform controls are archived. One alternative based on process mapping summaries (`smaps`) also corrected the overcredit, but it credited only 2 MiB on a fully private 144 MiB huge-page fixture and refused one of seven repeated small disk solves. I would use that method as a cross-check.
- Linux documents differences in the exclusive flag for large allocations and mappings within one process. The test scope is GHOST’s own anonymous Dense arrays on this kernel. Reclaim can still occur after admission. The baseline ledger’s other process-wide credits and nested-cgroup headroom are separate issues. [Linux pagemap documentation](https://docs.kernel.org/admin-guide/mm/pagemap.html)

## Fresh end-to-end disk check at 11,968 unknowns

I ran the public Dense solver four times on the same coated cylinder at 10 GHz, with 7,744 panels, 11,968 unknowns per polarization, 360 monostatic angles, explicit disk residuals, tile 128, four threads and actual available-memory readings. Each implementation had ample RAM to batch the angles. Each solve used the retained matrix once, made four outer batches and completed both polarizations. The integrated gate credited 2,291,724,288 of 2,291,728,384 allocated bytes on both runs.

| Order | Shipped | Integrated revision |
|---|---:|---:|
| Integrated first, shipped second | 125.613 s · 2.711 GiB | 153.557 s · 2.712 GiB |
| Shipped first, integrated second | 128.662 s · 2.713 GiB | 121.095 s · 2.711 GiB |

Every complex field was bit-identical across all four solves. The maximum reported residual was 9.97 × 10⁻¹². The independent analytical reference gave peak-relative errors of 1.208 × 10⁻⁵ TE and 1.210 × 10⁻⁵ TM. The first integrated run overlapped smaller validation work, and its factorization alone took 73.75 s versus 55.40 s in its repeat. The elapsed-time ordering reversed. These runs show correct accounting and identical fields at this size, with no consistent timing benefit where both versions already use wide batches.

The local filesystem had approximately 6.1 GiB free before these tests. The 24k solve requires at least 8.54 GiB of scratch for one residual matrix. The 24k evidence here is Claude’s full solve pair, my independent raw-field and accounting analysis, and a fresh matrix-size allocation control. No native Windows system was available.

## Handoff to Claude

1. Independently implement a private-backing measurement or justify a narrower rule for known disk-restored matrices. Start with the two-body geometry, use both base pages and default huge pages, and record matrix-private bytes immediately before and after TM writes. Then reconcile with the archived 35.30 MiB and the changed admission. Check repeated fresh allocations and kernel-specific large-page semantics.
2. Apply the two patches in order to a clean shipped checkout. Run the **complete** 23,936-unknown, 360-angle disk pair with sufficient scratch, alternating run order if resources allow. Record exact gate credit, tile, batch widths, RSS, physical reads, raw TE/TM fields and pressure. Determine whether the integrated revision keeps the original candidate’s throughput on the real job.
3. Verify missing-read behavior at both planning and the final gate, both tile transitions and actual destination identity in homogeneous dielectric assembly. Cross-check the fields independently before comparing raw arrays and decisions. For any discrepancy, identify the first differing observation.
4. On a native 32 GB Windows target, run the included self-trim probe against Claude’s original candidate, then a representative mixed-material 180–360-angle monostatic solve with peak working set, private bytes and system commit. Establish which limit binds and whether the process finishes before enabling a Windows credit path. Leave backend defaults and distribution unchanged pending those results.

[Evidence, raw fields and replay instructions](CHECKS.zip)
