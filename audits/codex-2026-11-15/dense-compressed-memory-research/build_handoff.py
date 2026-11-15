"""Build the review handoff from recorded measurements and array comparisons."""
import json,statistics
from pathlib import Path
HERE=Path(__file__).resolve().parent
def read(name):return json.loads((HERE/name).read_text())
a=read('analysis.json');rows={r['case']:r for r in a['summary']}
def table(headers,data):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in data])
def medians(filename,modes):
    d=read(filename)['records'];out=[]
    for t in (1,4):
        for n in (16,180):
            out.append([t,n]+[f"{statistics.median(r['seconds'] for r in d if r['threads']==t and r['rhs']==n and r['mode']==m):.4f}" for m in modes])
    return out
scale=[]
for n in (8192,16384,32768):
    for p in ('none','construction'):
        r=rows[f'star-{n}-180-compressed-{p}']
        scale.append([n,p,f"{r['retained_factor_bytes']/2**20:.1f}",f"{r['factor_peak_gib']:.3f}",f"{r['peak_gib']:.3f}",f"{r['assembly_seconds']:.2f}",f"{r['factor_seconds']:.2f}",f"{r['solve_seconds']:.2f}",f"{r['compute_seconds']:.2f}",r['refinement_steps']])
sweeps=[]
for name,r in rows.items():
    if name.startswith('star-4096-360-'):
        s=r['sweep_compression']
        sweeps.append([name.removeprefix('star-4096-360-'),s.get('solved_columns','—'),f"{r['solve_seconds']:.3f}",f"{r['compute_seconds']:.3f}",f"{r['peak_gib']:.3f}"])
dense=[]
for name in ('star-8192-180-dense-full','repeat-star-8192-180-dense-full','star-8192-180-dense-blocked','repeat-star-8192-180-dense-blocked','star-8192-180-dense-blocked_c','layout-star-8192-180-full','layout-star-8192-180-blocked'):
    if name in rows:
        r=rows[name];dense.append([name,f"{r['solve_seconds']:.3f}",f"{r['compute_seconds']:.3f}",f"{r['peak_gib']:.3f}"])
materials=[]
for name in ('pec20ft','coated','multilayer','partial','cavity','dielectric_star','multilayer-TM'):
    r=rows['capture-'+name+'-dense-none'];d=read('results/capture-'+name+'-dense-none.json')
    materials.append([name,d['spec']['length_m'],d['spec']['frequency_ghz'],r['panels'],r['unknowns'],f"{r['condition_est']:.1f}"])
maxden=max(r.get('max_per_angle_density_relative_error',0) for r in a['comparisons']);maxfield=max(r.get('peak_normalized_field_error',0) for r in a['comparisons'])
both=[]
for name,stem in (('pecsmall','pecsmall-both'),('multilayer','multilayer-both'),('dielectric','dielectric_both')):
    d=read('results/layout-'+stem+'-dense-none.json')
    restores=sum(x.get('research_restore_calls',0) for x in d['factors'])
    if name=='dielectric':assert restores>=1
    both.append([name,d['metadata']['assembled_system_reuses'],restores,d['metadata']['quality_gate']['passed']])
output=[]
for ref,name in (('star-8192-180-dense-full','output-star-8192-180-full'),('star-4096-360-dense-off-batch16','output-star-4096-360-batch16'),('repeat-control-star-4096-360-batch16','repeat-output-star-4096-360-batch16'),('star-4096-360-dense-off-batch256','output-star-4096-360-batch256')):
    for label in (ref,name):
        r=rows[label];output.append([label,f"{r['solve_seconds']:.3f}",f"{r['compute_seconds']:.3f}",f"{r['peak_gib']:.3f}"])
text=f'''# Dense and Compressed memory/workflow research — Claude handoff

Parent: `27afe8f3fb523a0a61f2a99ebb77e9e2708f16d7`.
Research branch: `codex/dense-compressed-memory-research-2026-11-15`.
Production files, native binaries, solver thresholds and user options are unchanged.

## Decisions supported by this work

1. **Do not enable inverse packing by default.** At 32,768 unknowns it reduced
   retained inverse bytes by 41.9%, but whole-process peak RAM by only 7.3%
   (3.682 to 3.414 GiB). The 180-angle solve became 25.9% slower and total
   compute time 2.7% slower. This is a possible memory-pressure option; it is
   not a general speed improvement or a 42% reduction in required machine RAM.
2. **Do not promote residual row-blocking alone.** The paired physical-matrix
   microbenchmark favors the existing full product. A single whole-solve timing
   that looked favorable was not sufficient evidence. Persistent C-order
   coefficients are a separate follow-up experiment, reported below. The more
   promising Dense candidate is **F-order multiplication output for narrow
   RHS batches**, which needs no coefficient conversion or extra full matrix.
   In the 4,096-unknown, 360-angle, 16-column-batch case, total compute time
   improved 12.3% and 12.5% in two order-reversed comparisons at unchanged RAM.
   Wide-batch and thread-count results prevent a blanket default change.
3. **Keep Dense and Compressed.** Compressed completed 32,768 unknowns and 180
   monostatic angles at 3.68 GiB here. Two dense complex128 matrices alone at
   that size occupy 32 GiB. Disk residual storage can remove one resident
   coefficient copy, but it does not make the LU factor itself out-of-core.
4. **Keep batching and disk conclusions workload-specific.** We tested 180 and
   360 actual monostatic directions and both automatic/off RHS compression.
   Narrow batches can trade memory for additional products and lost RHS-basis
   reuse. The measured disk control includes real reads, but is not a desktop
   memory-pressure experiment.

## What ran and how strong the evidence is

{a['cases']} fresh case processes were attempted; {a['completed']} completed.
Failed cases: `{json.dumps(a['failures'])}`. There are {len(a['comparisons'])}
saved-array comparisons. Their largest per-angle density relative error is
{maxden:.6g}, and largest peak-normalized complex-field error is {maxfield:.6g}.
The predeclared limits were 1e-7 and 1e-8 respectively; RHS matching uses 5e-15.

The star runs freshly assemble exact coefficient rows (64 separately seeded
random rows plus trace anchors) and check every original illumination at a
1e-12 normwise backward-error limit. These are additional sampled equations,
not a full exact matrix reference. The material runs keep production condition
and strict discrete quality gates. All four normal/transpose/adjoint cases
also compare against fresh full Dense matrices, including a lossless epsilon=12
dielectric. `analysis.json` is **array replay**, not another independent solve.

The 16,384- and 32,768-unknown packing comparisons use baseline Compressed plus
fresh exact-row checks. There is no fresh full Dense reference at those sizes
in this study. Mesh convergence, analytic scattering agreement, three-dimensional
objects, Windows DLL performance and a 32 GB desktop are **not** certified here.

Numerical jobs ran serially in fresh processes. Environment: 16 GiB cgroup,
four-CPU quota, one assembly/BLAS thread except the requested and reported
four-thread PEC20ft cases and labeled microbenchmarks. No new native compilation
was needed. `environment.json` verifies 278 unchanged production files;
`source_dependencies.json` verifies the inherited harness against the parent tree.

## Geometries and materials

All cases are **2-D P1 Galerkin** problems. Panel counts are not universally
unknown counts. The actual physical-material test dimensions are:

{table(['Case','Size m','GHz','Panels','Unknowns','Dense condition estimate'],materials)}

PEC20ft is a 6.096 m (20 ft) diameter circle at 2 GHz, TE. The other physical
cases have a 0.3 m nominal outer size at 5 GHz. Coated: PEC core, radius ratio
0.7, dielectric epsilon=4-0.2i. Multilayer: outer epsilon=4-0.2i, middle radius
ratio 0.85, inner epsilon=9-0.3i, PEC core radius ratio 0.65; both TE and TM
are checked. Partial coating has bare PEC, coated PEC and dielectric junctions.
Cavity is a narrow concave PEC contour. The standalone dielectric star has
seven lobes, epsilon=4-0.2i. Relative permeability is one. Exact generated
coordinates and material tables are in the evidence `.geo` files.

The scaling star is a different, five-lobed single dielectric interface:
r(theta)=1+0.2*cos(5*theta), epsilon=3-0.08i, TE. Unknown counts
4,096/8,192/16,384/32,768 correspond to 2,048/4,096/8,192/16,384 panels and
k*nominal-radius=40/80/160/320. Its circumscribed diameter is
15.3/30.6/61.1/122.2 air wavelengths. These are electrical-scale benchmarks,
not four separate asserted meter dimensions. We have not demonstrated a
20-foot, complex multilayer object at 15–18 GHz in this study.

## Compressed inverse packing

The process-local prototype packs only completed inverse-node `v12`, `v21`,
`e1`, `e2` arrays to complex64. Leaf and Woodbury-correction LU stay complex128;
the authoritative retained operator and all acceptance gates stay unchanged.
Construction packing means parent inverses use packed children. Finite and
nonzero-to-zero checks reject unsafe casts; casting workspace is admitted.
Post-build packing is separately measured at 8,192 unknowns.

{table(['Unknowns','Packing','Inverse MiB','Factor peak GiB','Process peak GiB','Assembly s','Factor s','Solve s','Compute s','Refinement steps'],scale)}

These are individual scale trials, not statistical confidence intervals.
At 16,384 unknowns, assembly also varied between trials; do not attribute that
variation to inverse packing. At 32,768, assembly was essentially unchanged
(401.83 versus 403.70 s); refinement increased from three to five steps.
The operator alone retained 2,006,649,760 bytes at that size, more than twice
the baseline inverse's 974,777,536 bytes. Packing the inverse cannot remove
the operator, assembly workspace, or angle-sweep buffers.

The 8,192-unknown controls were repeated in reverse order. Stage and final
high-water RSS include the validation harness; final RSS may also include
archive work. Batch RSS is captured before saving that batch. Retained bytes,
construction accounting, sampled RSS, and process high-water RSS are different
metrics and are preserved separately.

## Dense residual products and persistent coefficient layout

Physical 8,192-square matrix; four alternating-order repeats per configuration.
Median product seconds, with existing F-order coefficients:

{table(['Threads','RHS columns','Full','Rows256','Rows256 + C copy'],medians('residual-benchmark.json',('full','blocked','blocked_c')))}

The exploratory layout prototype keeps one persistent C-order original matrix
and reuses the owned F-order assembly buffer for in-place LU. This still has
two dense matrices; it is not a quadratic-memory reduction. It requires an
owned writable F-order input and explicit RAM residual storage. Matrix-copy
admission uses the production lock/check. It preserves physical coefficients,
condition scaling, residual checks and restoration of the shared assembly buffer.

Paired persistent-layout product medians (both layouts resident in this
microbenchmark, so these timings are not a memory-capacity demonstration):

{table(['Threads','RHS columns','F full','C full','C rows64'],medians('residual-layout-benchmark.json',('F_full','C_full','C_block64')))}

Full 8,192-unknown / 180-angle Dense trial measurements:

{table(['Case','Solve s','Compute s','Peak GiB'],dense)}

The layout check validates physical coefficients and bitwise restoration,
normal/transpose/adjoint solves, a zero RHS column, and LU buffer aliasing.
Production dual-polarization checks additionally recorded:

{table(['Case','Assembled-system reuses','Prototype restore calls','Discrete gate passed'],both)}

The PEC/multilayer cases reused assembled data but did not restore the same
coefficient buffer. The added dielectric lifecycle case explicitly exercises
that restoration path; the nonzero call counter is required by this report.

These are research prototypes, not complete production integrations. Any
promotion needs a repeatable end-to-end benefit on target BLAS/hardware and
tests for cancellation, allocation failure, concurrent admissions, unowned
inputs and fallback/disk policies. Material-run timing includes full-density
serialization inside the solve recorder; use those runs for accuracy/lifecycle
checks rather than a clean performance ranking.

### Follow-up: change product output layout without copying coefficients

The C-order result motivated a further exploratory check, not part of the
initial plan: `X.T @ A.T` transposed back, or `matmul(A, X, out=F_output)`.
Both keep the original coefficient matrix. Paired product medians:

{table(['Threads','RHS columns','F full','C full','Transpose formulation','F output'],medians('residual-output-benchmark.json',('F_full','C_full','F_transpose','F_output')))}

The F-output prototype allocates only the usual product-sized result; it adds
no n-by-n matrix and no coefficient conversion. It preserves residual checks.
The small-batch products improve substantially here, but the 180-column,
four-thread case does not. Do not turn that into a universal output-layout rule.
Full-solve controls (RHS compression off for the 360-angle comparison):

{table(['Case','Solve s','Compute s','Peak GiB'],output)}

The narrow-batch pair was repeated in reverse order. These full-solve trials
and a production dual-polarization dielectric case
are included in the array comparisons. A narrow-batch output policy is a
better follow-up candidate than copying the whole coefficient matrix, but
needs paired repeated whole-solve trials on other BLAS/thread configurations
before production promotion. Its result must be separated from the slower
row-blocking prototype and the persistent C-matrix prototype.

## 360-angle batching

Angles 0 through 359 degrees, same geometry and one factor per process.
The label `off` means RHS compression is disabled; otherwise it is automatic.
All original columns are validated, even if fewer basis columns are solved.

{table(['Configuration','Solved RHS columns','Solve s','Compute s','Peak GiB'],sweeps)}

The 180-angle cases cover -90 through 89 degrees. Neither sweep duplicates
its endpoint. Keep full-angle work, batch width, automatic RHS compression,
and refinement counts separate when explaining speed differences.
None of these 360-angle controls reduced the number of solved RHS columns;
lost basis reuse is a possible batching interaction, not the measured cause
of the slowdown in this particular suite.
Even with F-order output, the 16-column Dense batches remained slower overall
than the wide-batch control. This improves a RAM-saving configuration; it does
not justify shrinking batches when the wide sweep already fits comfortably.

## Disk control

`disk-residual-benchmark.json` uses the production ResidualSpool for a 1 GiB
physical matrix. Creation plus fsync took 2.13 s. With one thread, cached /
advised-evicted / cached-again product times were 0.298 / 0.430 / 0.294 s for
16 RHS and 1.452 / 1.455 / 1.462 s for 180 RHS. `/proc/self/io` recorded
1,073,741,824 read bytes for each advised-evicted product and zero for cached
controls. File-cache advice is local to our temporary file. The original
matrix remained resident; no global cache was dropped and no 32 GB pressure
or out-of-core LU was simulated. NVMe/Windows results may differ substantially.

## Evidence correction and reproduction

The original material recorder hooked the base CompressedFactor.solve, but
HMatrixFactor overrides it. Original fields, quality gates and measurements
are preserved; those runs did not capture Compressed densities. The corrected
runner explicitly hooks HMatrixFactor and repeats all 21 cases under `capture-`
labels. It changes no numerical solver. See `CAPTURE_NOTE.md`.

Read `README_REPRO.md` for commands. `evidence/MANIFEST.json` indexes split
lossless evidence; `unpack_evidence.py` verifies archive and per-array hashes.
All full RHS, density, complex-field and exact-row residual arrays are retained,
along with original result JSON, stdout/stderr, geometry and return codes.
Original NPZ hashes identify source containers; restored numerical values and
C/F layouts are checked bitwise by `verify_evidence.py`. Regenerated ZIP bytes
need not match. Replayed analysis must match the original analysis as well.

## Independent review requested from Claude

**First state your own hypotheses and acceptance criteria, then perform fresh
checks independently, and only then cross-analyze our evidence.** Label each
finding as fresh solve, fresh equation evaluation, saved-array replay, source
inspection, or another model's measurement. Agreement between models is not
an additional numerical validation.

1. Reproduce the memory/speed tradeoff using independent peak measurements and
   a larger, more difficult geometry. Does construction packing make an
   otherwise rejected memory-capped solve finish, with all original gates?
   Check near-limit admission, rebuilds, and retained-array byte accounting.
2. Stress packing on high-contrast, low-loss/resonant multilayers and junctions,
   both polarizations and adjoint condition probes. Use fresh Dense anchors
   where feasible and new independently seeded exact rows elsewhere. The
   current large-scale evidence is one dielectric star family.
3. Prioritize the no-coefficient-copy Dense output-layout candidate, especially
   narrow batches. Independently assess the persistent C-order layout too. Does it improve
   actual 180/360-angle runs on another BLAS/thread configuration after counting
   copy/restoration costs? Verify shared-polarization lifecycle, cancellation,
   failures and admission before proposing production code. Reject it if the
   gain is marginal or unstable.
4. Cross-check batching with automatic RHS compression both on and off. Can a
   memory-aware batch policy save useful RAM without losing more in repeated
   operator work or RHS-basis reuse? Preserve original-angle validation.
5. For larger Compressed wins, profile the retained operator and its assembly
   rather than assuming inverse storage dominates. Investigate reusable/nested
   far-field bases or bounded temporary assembly only with measured rank,
   accuracy and total-memory accounting; no savings are established for these
   proposals here. For Dense, test real local-storage pressure before extending
   disk policy. Fully out-of-core LU would be a separate, much larger project.

FMM was not rerun in this handoff. Continue its independent review separately;
these Dense/Compressed results neither validate nor invalidate an FMM speedup.
Do not merge a research hook or change a user-facing default on the strength of
retained-byte counts or a single favorable timing.
'''
(HERE/'HANDOFF_DENSE_COMPRESSED_RESEARCH.md').write_text(text)
print('Wrote handoff',len(text),'characters')
