# GHOST backend accuracy, time and peak memory

On shipped main at `ed90b65`, Dense and Compressed reproduced independent analytical fields for the 2-D cylinders tested here. Refining the source geometry changed the answer much more than switching backends. On the 8 GHz ellipse, Dense was faster and Compressed used less peak process memory. The geometry and number of unknowns matter when applying those results to a larger model.

## Accuracy against independent references

Each case used the public solver with both polarizations. Moving the cylinders away from the origin made the complex phase vary with the incident angle. Reference calculations enforced the cylindrical boundary conditions mode by mode and checked convergence of the analytical series. Percentages are maximum absolute complex-field error divided by peak reference magnitude, taking the worst angle, polarization and backend. They are field-amplitude errors, not percentage errors in RCS power.

| Cross-section | 2 GHz, 180 incident angles, coarse → fine | 15 GHz, 360 incident angles, coarse → fine |
|---|---:|---:|
| PEC circular cylinder | 0.2424% → 0.0151% | 0.1291% → 0.0301% |
| Homogeneous lossy magnetic dielectric cylinder | 0.6538% → 0.0397% | 0.0552% → 0.0154% |
| PEC core with a lossy magnetic dielectric coating | 1.2883% → 0.0784% | 0.2739% → 0.0682% |

The outside radius was 0.08 m, and the coated cylinder’s core radius was 0.05 m. At 2 GHz the exterior used 96 and 384 panels. At 15 GHz it used 384 and 768. The core boundary used 60 and 240 panels at 2 GHz and 240 and 480 at 15 GHz. These are analytical benchmarks for infinite 2-D cylinders. All fixed-mesh jobs passed the discrete quality checks. On the finest coated case, the hierarchical Compressed path ran on 2,016 unknowns. Across the coated study, the maximum Dense–Compressed relative field difference in the L2 norm was below `1.84e-11`.

**Default mesh certification.** I also used the GUI’s backend dispatch with Automatic, the standard accuracy target and 180 incident angles at 2 GHz. On a translated dielectric cylinder described by 96 straight edges, Dense was selected and both polarizations were certified on refinement from 96 to 144 panels. Their largest base-to-fine complex change was 0.0080%, while the worst error against the ideal circle was 0.647%. Starting with 192 input vertices and repeating the same policy reduced that error to 0.160%. The calculation can converge on the supplied polygon while some error remains in the representation of its curved boundary.

## Efficiency on a noncircular dielectric

This separate case was an ellipse measuring 0.20 m by 0.12 m at 8 GHz, with relative permittivity 2.5 − 0.04i and relative permeability 1. Each run solved both polarizations on 768 panels with a largest system of 1,536 unknowns. The 180-angle grid ran from −90° through +89° and the 360-angle grid from 0° through 359°. The discrete residual and condition checks were enabled. Explicit backend selection and the same batch size and thread counts allowed direct comparisons.

| Incident angles | Backend | Median solver time | Both times | Median peak process RSS |
|---:|---|---:|---|---:|
| 180 | Dense | 4.78 s | 5.10, 4.47 s | 174.8 MiB |
| 180 | Compressed | 7.13 s | 7.00, 7.25 s | 153.7 MiB |
| 360 | Dense | 5.50 s | 5.35, 5.65 s | 172.0 MiB |
| 360 | Compressed | 7.98 s | 8.35, 7.62 s | 153.4 MiB |

The eight timed solves ran sequentially in fresh Linux processes, with order reversed on the second pass. Each used one pinned CPU, one assembly thread and one BLAS thread. The timer includes assembly, factorization, both polarizations, all right-hand sides and the quality checks. Peak RSS includes the worker and its libraries. Startup and final file export are outside the timer. Two observations per configuration establish the comparison on this machine, with visible run-to-run variability.

Both Compressed configurations recorded the actual hierarchical-matrix backend. The largest difference between Dense and Compressed, normalized to the Dense peak, was `2.52e-12`. The overlapping physical angles of the half- and full-circle studies agreed to within `6.6e-15`. In contrast, doubling the panel count in a separate 360-angle Dense run changed the field by up to 0.0268% of the refined peak. That is a mesh-sensitivity measurement. The ellipse has no independent analytical reference in this test.

For context, the earlier 5 GHz coated PEC study measured 1.246 GiB and 35.7 s with Dense versus 0.517 GiB and 43.2 s with Compressed at 5,883 unknowns and 180 angles, for one polarization. This archived result and the fresh ellipse both favor Dense for elapsed time and Compressed for memory on their respective fixtures. The size of the memory saving differs substantially. [Earlier integration review and data](https://github.com/14cole/20261028_GRIM/tree/7a5e9fdabe0e22de1fd74ef01bb4a22f07567733/audits/claude-2026-11-17/hmatrix-production-integration-review)

## Scope and next decision

These measurements are for the 2-D backend on Linux. All 528 shipped files matched the pinned GitHub identities. This review makes no production changes. A representative large, mixed PEC/dielectric model on the intended 32 GB Windows desktop, at 180 and 360 incident angles, is still the key missing measurement for capacity and turnaround time. Retain the full complex fields, determine mesh sensitivity, and measure wall time and peak process memory before deciding whether a backend optimization improves that workflow. The earlier 65,536-unknown, two-incident-direction research case cannot establish a full-sweep desktop capacity.
