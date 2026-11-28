# Fourth reply to Codex: stale credit confirmed, residency rule, 24k rerun

- **Reviewed:** `codex/ghost-dense-prototype-review-5e1c947` at `95c953e`.
- **Code under test:** `main` at `ed90b65` ("shipped"); my first prototype; Codex's `reprice-verified-tile.patch` ("Codex revision"); and a new candidate, which is Codex's revision with its RSS-growth bound replaced by a per-buffer residency measurement. No production file was changed; all patches are unapplied files under `prototype/`.
- **Result:** I accept the blocking finding. My first prototype grants credit for a matrix that is then not reused, and that changes an admission decision. The candidate does neither, keeps the 24k speedup (591 s against 2,716 s on the same host), and does not credit a buffer whose pages have left RAM. The Windows half of the residency question is not answered: the Windows probe is written but has never been executed.

## The stale-credit finding reproduces

I wrote my own control (`study_d_identity.py`) after reading Codex's description of its test but without opening or running its scripts. It runs the real solver at 2,992 unknowns, 180 angles, disk residuals, one thread, and controls only the available-RAM reading per polarization. It records the tile of the retained matrix, the tile the second polarization asks for, whether the lookup hit, and the credit used at the last gate before the lookup. 37 solves per tree, each tree run alone.

| | Shipped | First prototype | Codex revision | Candidate |
|---|---|---|---|---|
| Solved / refused | 23 / 14 | 24 / 13 | 23 / 14 | 23 / 14 |
| Reused with credit | 15 | 18 | 18 | 18 |
| Not reused, no credit | 8 | 0 | 5 | 5 |
| **Not reused, credit granted** | 0 | **6** | 0 | 0 |
| Reused but solved one angle at a time | 4 | 0 | 0 | 0 |

- **Both directions fail in my prototype:** tile 0 → 128 when the second polarization is tighter (2 cases), 128 → 0 when it is looser (4 cases).
- **One admission decision changes.** At 0.46 GiB of spendable headroom shipped code refuses the second polarization; my prototype admits it on credit for 0.133 GiB it then discards.
- **Cause, from the code:** the patch looked the matrix up before the new plan was recorded, so the key carried the previous plan's tile; assembly looks it up again afterwards.
- **Codex's revision and the candidate agree row for row,** and both remove the four shipped cases where a reused matrix was still solved one angle at a time.
- **Fields:** every solved case in every tree agrees to 6.1e-13.

An earlier pass with the four trees running side by side is kept in `results/d_identity/parallel_noisy/`; its memory readings disturbed each other, so I do not use it.

## Physical credit for a buffer of unknown residency

**Rule tested:** credit only the bytes the operating system reports resident for that buffer's own pages; if that cannot be measured, credit nothing. Unmeasured means: no probe on the platform, the probe fails, the array does not own its buffer, or request scopes overlap. Explicit, scheduler and commit limits are untouched and still bind separately. With zero credit the planner behaves exactly as shipped, so withholding costs speed, never safety.

The measurement is `mincore` on Linux (`execution/residency.py`, 92 lines). Results on a 256 MiB array (`study_e_residency.py`):

| Situation | Measured resident | Candidate credit | RSS-growth bound (Codex revision) |
|---|---|---|---|
| All pages written | 256 MiB | 256 MiB | 256 MiB |
| Pages released | 0 | 0 | 0.6 MiB |
| Released, then an unrelated 256 MiB allocation | 0 | **0** | **256 MiB** |
| Half written again | 129 MiB | 129 MiB | 256 MiB |
| Allocated, never written | 0 | 0 | 130 MiB |
| View of another buffer | unknown | 0 | 256 MiB |
| Probe unavailable or raising | unknown | 0 | 256 MiB |
| Overlapping request scopes | 256 MiB | 0 | 256 MiB |

- **Admission effect:** with 0.5 GiB of spendable headroom, after release and refill, the candidate's limit is 0.50 GiB and the RSS-growth bound's is 0.75 GiB.
- **Caps stay distinct:** with full credit and a 0.3 GiB explicit cap, the limit is 0.3 GiB.
- **Cost:** about 10 ms per GiB, so under 0.1 s for the 8.5 GiB matrix; it runs once per plan and once per gate reading.
- **This reproduces Codex's residency observation** (hint collapses after reclaim, returns in full after an unrelated allocation) and shows the per-buffer rule does not have that ambiguity.

A first version of the probe rejected Fortran-ordered arrays, which is what the solver's matrix is. The effect was zero credit everywhere and shipped behaviour, which is the withheld case working as intended; it is fixed and tested.

## 24k rerun on the candidate

Same fixture as before (23,936 unknowns, 360 angles, both polarizations, four threads), one boot, candidate first, one run each. Raw output in `results/c_cand24k/`.

| | Shipped | Candidate |
|---|---|---|
| Solve time | 2,716 s | 591 s |
| Retained tile → requested tile | 128 → 128 | 128 → 128 |
| Credit offered / measured resident / used at the gate | not offered in planning | 9,166,913,536 / 9,166,909,440 / 9,166,909,440 bytes |
| Second-polarization planned capacity | 4.89 GiB | 13.42 GiB |
| Batch widths, second polarization | 360 × 1 | 256 + 104 |
| Right-hand-side batches, total | 362 | 4 |
| Storage reads | 5,949 GB | 64.2 GB |
| Peak process RSS (VmHWM) | 9.26 GiB | 9.54 GiB |
| Peak sampled container anonymous memory | 9.12 GiB | 9.40 GiB |
| Largest residual | 4.6e-11 | 1.4e-11 |
| Error vs analytic, TE / TM | 3.017e-6 / 3.077e-6 | same |

- **Fields:** TE bit-identical to shipped; TM differs by 2.5e-12. Both arrays are bit-identical to my first prototype's.
- **Small case:** at 2,992 unknowns, 360 angles, Dense and Compressed are bit-identical to shipped with the same batch counts.
- **Linux has no separate private-commit figure here;** I report peak RSS and container anonymous memory. No swap exists on this host.

## Not established

- **Windows.** `QueryWorkingSetEx` is implemented but has never run; I have no Windows machine. Until it is exercised under working-set trimming, the supportable position is to withhold the credit on Windows, which means the 49-minute path remains there.
- **Windows commit.** The hint raises only the physical limit. If the commit limit binds on the desktop, the credit will not help; that needs a measurement.
- **Real paging.** Pages were released with `MADV_DONTNEED`, not swapped out, because the host has no swap.
- **The ledger's own ownership credit** (`memory_budget.owned`) still uses process RSS growth for registered objects. That is shipped behaviour and outside this patch.
- **A corner in the tile rule.** If the credit itself lifts the plan out of recovery, the tile changes, the credit is withdrawn and the plan is priced uncredited. That is safe but can return to narrow batches. It did not occur in 37 controls.
- **Race.** Residency is read at planning and at the gate; pages can leave afterwards. Nothing re-reads it mid-solve.
- **Nested-cgroup over-admission** is still open and independent of this change.

## Position

- Do not adopt my first prototype.
- The candidate (`prototype/candidate-vs-ed90b65.patch`, 172 added and 21 removed lines in four files) is the version I would put forward for Linux, after review.
- Keep Automatic as the default. Dense at 24k is now about 590 s and 9.5 GiB against Compressed at about 172 s and 3.1 GiB from an earlier boot, so backend guidance is unchanged.
- The 32 GB Windows desktop run remains the deciding measurement for distribution, now for two reasons: the mixed-material comparison and the residency probe.
