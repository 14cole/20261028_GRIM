# Large geometry recommendations for implementation review

This package contains audit experiments and evidence, not a production solver patch. Read [the audit](../large_geometry_ram_speed_audit.md), [the Claude comparison](../large_geometry_comparison_with_claude.md), and [measurements](measurements.json). No production defaults, physical models or numerical acceptance limits were changed.

Implementation follow-up: the four priority-one changes and the priority-two idle-worker release option are now implemented in the working tree. See the separate [implementation and qualification package](../large_geometry_implementation_20261029/README.md), including its explicit remaining-work list. This original experiment package and its measurements remain historical evidence; they do not describe the newer optional-upgrade policy.

## Prioritized changes

| Priority | Proposed change | Required qualification |
| --- | --- | --- |
| 1 | Account explicitly for GMRES basis/work arrays at the selected angle batch size | Force the GMRES path at batches 1, 8, 16, 64 and 256; measure live arrays and verify the forecast covers both ordinary refinement and correction paths. |
| 1 | Re-admit tile fallback after an H-matrix assembly rejection | Force rank, sampled-error and storage rejection. Verify stale resources are released and tile workers/workspaces fit before construction. Reject cleanly if they do not. |
| 1 | Choose a smaller angle batch before refusing a solvable operator/factor | Compare fields and convergence for multiple batch sizes. Preserve one factor across batches; price the GMRES path independently of ordinary RHS work. |
| 1 | Upgrade preconditioner accuracy when iteration cost justifies it and memory admits it | Reproduce the 1e-8/1e-10 inlet comparison; expand to PEC, lossless/lossy/magnetic, near-resonant, thin-gap and multi-region cases. Keep final operator/residual/sample-row gates. Do not globally tighten solely from this case. |
| 2 | Release idle tile-worker pools or spill inactive H-matrix partners under memory pressure | Test transitions between tile and H-matrix meshes, cancellation, cleanup, reload failure and material-specific paired assembly. Report actual saved memory and additional I/O/restart time. |
| 2 | Reuse reciprocal H-matrix kernel queries | Confirm formulation-specific signs, direction, polarization, transpose/adjoint and near corrections; compare all operator/field families. Bound cache memory and in-flight tasks. |
| 2 | Reuse compatible P2/P3 hierarchical assembly | Implement sparse projection or reusable query data without densifying. Preserve exact-near treatment and independent operator/sample-row validation. Price retained fine operators and projection work. |
| 2 | Improve rank/phase/refinement forecasts and Automatic's time/memory choice | Use matched records; preserve underestimation margins. Surface storage/rank risks separately. Do not treat initial refinement candidates as guaranteed final resource requirements. |
| 3 | Add a capacity-oriented iterative solver with the existing H-matrix product | Use a bounded near-field/overlapping/coarse preconditioner; record restart, iteration count, true residual, sample-row errors and conditioning. Reject nonconvergence without silently weakening gates. |
| 3 | Add active operator/factor block storage, followed by FMM or directional operators where justified | Design bounded cache and scratch admission, query/solve compatibility, checksums and failure cleanup. Benchmark disk bandwidth and repeated passes. Validate material/derivative/basis/near-field physics for a new FMM implementation. |

## Specific evidence to review

The stronger-preconditioner comparison consists of `high_contrast_compressed_1g`, `high_contrast_tight_1g` and both `_repeat` cases. The baseline final TE/TM inverses occupy about 144/145 MiB; the tighter ones about 171/171 MiB. Final-mesh GMRES columns fall from 303 to zero. The median full certified call falls from 57.60 to 37.19 seconds. This is an inverse-build accuracy experiment; production acceptance remains unchanged.

The angle-batch comparison is `airfoil_b256` against `airfoil_b64`. The sampled RSS reduction is about 250 MiB, with the same final 13,618-unknown maximum system and passed mesh certification. It has one fresh run per configuration and should be repeated across more workloads before becoming an automatic timing policy.

Source review should pay particular attention to `compressed/runtime.py` fallback transitions, `compressed/memory.py` solve workspaces, `compressed/factor.py` GMRES allocation and refinement behavior, `compressed/worker_pool.py` retained lifetimes, and `execution/policy.py` dense preference. Source hashes are saved separately for reproducible review.

The synthetic inlet geometries are deliberately simple. Neither their success nor their memory consumption certifies a real coated duct, an arbitrary resonant cavity, or a finite 3D object. Use the actual engineering geometry for the next acceptance benchmark.
