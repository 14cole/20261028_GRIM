# Native Windows Dense comparison

Use a 64-bit Python environment with the repository's runtime dependencies and `psutil` on the intended 32 GB Windows desktop. The runner captures observed physical RAM, so the result identifies the actual machine capacity. It uses the current physical and commit limits and the installed paging-file policy. Keep those settings constant across the comparison.

The script takes separate shipped and corrected source trees, Claude's fixture harness, and a new output directory. To prepare them from a clone with this review branch and the Codex audit fetched, run the following in PowerShell from the clone root. Substitute the downloaded script’s absolute path for `windows_dense_ab.py` if it is in another directory. The input commits are immutable. The five solver files affected by the two patches are checked against recorded hashes before computing.

```powershell
git -c core.autocrlf=false worktree add --detach ..\ghost-shipped ed90b65ff89826274adacae01bcfbafe143e9819
git -c core.autocrlf=false worktree add --detach ..\ghost-corrected ed90b65ff89826274adacae01bcfbafe143e9819
git -c core.autocrlf=false worktree add --detach ..\ghost-evidence 6a7bdc98f43c88c991758c2445f8c445741e84b8
$audit = (Resolve-Path "..\ghost-evidence\audits\claude-2026-11-26\ghost-backend-audit").Path
$codex = (Resolve-Path "..\ghost-evidence\audits\codex-astra\ghost-residency-review-d0b732f").Path
git -c core.autocrlf=false -C ..\ghost-corrected apply "$audit\prototype\candidate-vs-ed90b65.patch"
git -c core.autocrlf=false -C ..\ghost-corrected apply "$codex\private-matrix-reuse.patch"
python windows_dense_ab.py ..\ghost-shipped ..\ghost-corrected "$audit" ..\ghost-windows-results --repeats 2
```

The default fixture has two separated PEC cylinders, different lossy dielectric coatings, 4,224 outer sides per cylinder and 10 GHz incidence. The requested sweeps are −90° through 89° and 0° through 359°, both with one-degree spacing. Each run solves both polarizations on the fixed mesh using Dense, four threads and automatic residual storage. Repeating twice reverses run order for each angle count. For a user's own geometry in metres, append `--geometry C:\path\to\model.geo --ghz 10`. For a small warm-up use `--sides 192 --angles 180` with a different output folder. Disk availability, ordinary background applications and the page-file settings influence the real desktop result.

`summary.json` records outcomes, solver and process times, batch counts and full-field differences for each pair. Individual runs store the full complex TE/TM arrays, the memory ledger, detailed estimates and errors. The parent samples process and system counters at 0.25-second intervals. Windows process high-water counters give peak working set and peak private commit. The largest sampled system-wide commit and smallest sampled commit headroom also include other processes. System-wide extrema can occur between samples. A nonzero command exit denotes a failed solve or missing Windows counters. Inspect each pair's numerical deltas and gate evidence before drawing a performance or admission conclusion.

The corrected patch intentionally gives zero new physical reuse credit on Windows. This comparison measures the consequence on a real job, including a possible second-polarization refusal. Running on Linux with `--linux-smoke` exercises the solve, comparison and serialization code but leaves the Windows-only fields unmeasured.
