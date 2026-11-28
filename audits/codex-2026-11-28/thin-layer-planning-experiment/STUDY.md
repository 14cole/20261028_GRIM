# Thin dielectric planning on the physical midsurface

The prototype corrects a GHOST planning error that can either refuse a job unnecessarily or select the wrong memory model for Compressed. A named segment boundary in a continuous, homogeneous thin layer can split a node in the general interface mesh. The thin-layer field solver joins it again before assembling the matrix. The previous planner counted the split nodes. The experiment makes desktop, HPC and public solve admission price the joined mesh. [Experimental code](https://github.com/14cole/20261028_GRIM/commit/f1564a770151abd8fa0e98cc95700ca311443cad) · [Scripts, raw fields and memory forecasts](REPLAY.zip)

## What changed

The candidate prepares the oriented physical midsurface and records the original element order, so each polarization receives its own material records in the correct positions. Desktop and HPC can reuse that geometry across polarizations within a mesh-planning phase. Frequency-dependent material values and the actual memory check remain specific to each solve. Automatic backend selection, the inner memory check and field assembly now receive the same physical dimensions. The inner check also uses the operator storage model selected for that job. No user settings, external data files or reuse of past solves are involved.

## Numerical and operational results

| Experiment | Finding |
|---|---|
| Claude’s four-section thin layer | Desktop and HPC previously forecast 48 TE and 24 TM unknowns. The prototype forecast 42 and 21, exactly the dimensions factorized by Dense and used by Compressed for all 36 angles. |
| Multifrequency and angular sweeps | Across 72 measured operators, the old initial admission counts disagreed with execution 48 times. The prototype matched all 72. All 540 polarized result rows, including complex amplitude and residual, matched the baseline exactly. This covered monostatic, bistatic, fixed reference frequency and a dispersive material that changes its trace count. |
| Real Dense admission | On a 128-panel layer split into 128 named pieces, a 0.411 GiB configured reservation had previously refused the job. The prototype completed it. All 360 complex samples and residuals matched the ample-budget baseline. Both versions refused at 0.400 GiB. These limits were chosen to straddle the estimate. |
| Compressed operator boundary | On 1,022 panels the release forecast 1,024 TM unknowns and a hierarchical operator. Execution built a 1,023-unknown streamed-tile operator. The prototype forecast the correct family and its modeled peak rose from **236.89 to 334.12 MiB**. On 1,023 panels the system really had 1,024 unknowns and used the hierarchical operator. Both revisions produced identical complete fields for both fixtures. These numbers are modeled peaks, separate from actual process memory. |
| Automatic backend policy | For 4,998 panels, one, two or seventeen segment names now give 9,998 TE and 4,999 TM unknowns and select Dense at the controlled 24 GiB budget. The baseline chose Compressed for the two- and seventeen-name versions. At 4,999 panels the prototype still selects Compressed, as expected from the real 10,000 TE unknowns. These larger cases were planning only. |
| Forecast overhead | For the cold 4,998-panel, two-name forecast, three processes per revision measured median planning times of **0.65 s on the release and 0.72 s on the prototype**. The correctness fix adds geometry work. These shared-host measurements do not establish a whole-solve speedup. |

The edge suite exercised 22 cases, including closed and disconnected layers, reversed input, zero and magnetic contrast, material changes, certification and invalid geometry. All 48 successful channel arrays in that suite matched exactly. Six invalid configurations now fail during planning, including unsupported polynomial order, branching and geometry outside the thin-layer approximation. Existing ordinary impedance-sheet, closed impedance, PEC and bulk dielectric controls retained their forecasts. All 1,080 ordinary sheet samples matched.

## Scope and next decision

The prototype is based on the code candidate `6621db2` from PR #4. The release PR can proceed with user testing independently. This trial supports a separate integration of the thin-layer planning correction. In the cases tested, the changed forecasts affected admission and backend selection near decision boundaries. Establishing a new 32 GB desktop capacity limit would need full jobs under native Windows pressure. Physical accuracy of the underlying thin-layer approximation would need a separate comparison to a finite-thickness body.

The low-level standalone mesh formulation has no enclosing public solve from which to obtain a resource record and retains its previous standalone Compressed storage estimate. Direct raw-mesh numerical output was independently checked. The public desktop and batch paths are the ones covered by the operator-family fix. The reported region count in a rejection message may still include synthetic interface IDs for named pieces. The dimensions and the memory gate were checked independently of that diagnostic.

The archive includes the individual experiments with per-directory replay instructions. Start with `factors/` for the actual operators and the reservation boundary, `compression/` for the Compressed cutoff, and `routing/` for Automatic selection.

The replay archive contains 138 evidence files with a per-file SHA-256 manifest. Its SHA-256 is `b82239748b07cb1d6ffcfbf51b11c75bb6cf671a79126be984875e810ac57eec`.
