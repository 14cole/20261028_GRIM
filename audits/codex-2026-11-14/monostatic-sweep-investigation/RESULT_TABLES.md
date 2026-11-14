# Complete measurement tables

All times are seconds. Peak RAM is process high-water RSS in GiB. Compute
is setup + RHS + solve + matched projection, excluding extra audit validation
and array serialization. Measurements are single samples, not confidence intervals.

| Case | Unknowns | Angles | Setup | Solve | Compute | Peak GiB | Accurate A RHS-equivalents |
|---|---:|---:|---:|---:|---:|---:|---:|
| `slot-1024-180-TE-fmm-block8` | 1024 | 180 | 12.838 | 23.789 | 36.659 | 0.1313 | 7624 |
| `slot-1024-180-TM-compressed` | 1024 | 180 | 3.008 | 0.726 | 3.760 | 0.1411 | — |
| `slot-1024-180-TM-dense` | 1024 | 180 | 1.872 | 0.077 | 1.984 | 0.1255 | — |
| `slot-1024-180-TM-fmm-block8` | 1024 | 180 | 12.749 | 19.258 | 32.036 | 0.1317 | 6224 |
| `slot-1024-180-TM-fmm` | 1024 | 180 | 12.647 | 71.041 | 83.732 | 0.1319 | 5988 |
| `slot-1024-180-compressed-cold` | 1024 | 180 | 3.231 | 0.459 | 3.719 | 0.1309 | — |
| `slot-1024-180-dense-cold` | 1024 | 180 | 1.841 | 0.086 | 1.955 | 0.1261 | — |
| `slot-1024-180-fmm-cold` | 1024 | 180 | 13.678 | 101.211 | 114.927 | 0.1314 | 8140 |
| `smoke-compressed` | 256 | 4 | 0.604 | 0.002 | 0.608 | 0.0945 | — |
| `smoke-dense` | 256 | 4 | 0.448 | 0.001 | 0.450 | 0.0922 | — |
| `smoke-fmm` | 256 | 4 | 1.258 | 0.057 | 1.316 | 0.0930 | 16 |
| `square-1024-180-compressed-cold` | 1024 | 180 | 2.168 | 0.141 | 2.341 | 0.1174 | — |
| `square-1024-180-dense-cold` | 1024 | 180 | 1.348 | 0.092 | 1.466 | 0.1248 | — |
| `square-1024-180-fmm-cold` | 1024 | 180 | 15.643 | 45.572 | 61.249 | 0.1209 | 4539 |
| `star-2048-180-TE-fmm-block8` | 2048 | 180 | 29.067 | 113.741 | 142.870 | 0.1719 | 5960 |
| `star-2048-180-compressed-cold` | 2048 | 180 | 5.053 | 0.453 | 5.561 | 0.1685 | — |
| `star-2048-180-dense-cold` | 2048 | 180 | 3.655 | 0.456 | 4.171 | 0.2242 | — |
| `star-2048-180-fmm-batch8` | 2048 | 180 | 26.354 | 148.488 | 174.908 | 0.1783 | 8280 |
| `star-2048-180-fmm-cold` | 2048 | 180 | 25.853 | 201.787 | 227.704 | 0.1568 | 6366 |
| `star-2048-180-fmm-lgmres_cold-inner80` | 2048 | 180 | 27.177 | 217.467 | 244.705 | 0.1565 | 6524 |
| `star-2048-180-fmm-lgmres_cold` | 2048 | 180 | 27.947 | 256.485 | 284.516 | 0.1571 | 6941 |
| `star-2048-180-fmm-packed-inverse` | 2048 | 180 | 25.410 | 204.930 | 230.404 | 0.1555 | 6366 |
| `star-2048-180-fmm-recycle-inner80` | 2048 | 180 | 27.136 | 224.631 | 251.839 | 0.1569 | 6380 |
| `star-2048-180-fmm-recycle` | 2048 | 180 | 29.419 | 220.174 | 249.671 | 0.1569 | 6369 |
| `star-2048-180-fmm-rhs_qr` | 2048 | 180 | 27.681 | 102.641 | 130.418 | 0.1664 | 3110 |
| `star-2048-180-fmm-warm` | 2048 | 180 | 25.339 | 207.693 | 233.093 | 0.1562 | 6362 |
| `star-2048-180-full-compressed-cold` | 2048 | 180 | 5.696 | 0.554 | 6.313 | 0.1916 | — |
| `star-2048-180-full-dense-cold` | 2048 | 180 | 4.172 | 0.354 | 4.581 | 0.2431 | — |
| `star-2048-180-full-fmm-recycle` | 2048 | 180 | 26.087 | 214.847 | 241.028 | 0.1654 | 6683 |
| `star-2048-180-full-fmm-warm` | 2048 | 180 | 25.014 | 204.818 | 229.919 | 0.1655 | 6350 |
| `star-2048-360-compressed-batch16` | 2048 | 360 | 5.229 | 1.222 | 6.643 | 0.1681 | — |
| `star-2048-360-compressed-batch256` | 2048 | 360 | 5.088 | 0.804 | 6.035 | 0.2008 | — |
| `star-2048-360-compressed-cold` | 2048 | 360 | 5.503 | 0.912 | 6.530 | 0.1680 | — |
| `star-2048-360-dense-batch16` | 2048 | 360 | 3.581 | 1.330 | 5.098 | 0.2240 | — |
| `star-2048-360-dense-batch256` | 2048 | 360 | 3.547 | 0.765 | 4.421 | 0.2561 | — |
| `star-2048-360-dense-cold` | 2048 | 360 | 4.095 | 1.142 | 5.372 | 0.2240 | — |
| `star-2048-360-fmm-cold` | 2048 | 360 | 28.526 | 518.833 | 547.502 | 0.1570 | 12735 |
| `star-2048-360-fmm-lgmres_cold` | 2048 | 360 | 28.525 | 511.266 | 539.942 | 0.1568 | 13866 |
| `star-2048-360-fmm-recycle` | 2048 | 360 | 28.017 | 478.803 | 506.955 | 0.1571 | 12702 |
| `star-2048-360-fmm-rhs_qr` | 2048 | 360 | 26.725 | 215.201 | 242.106 | 0.1793 | 6230 |
| `star-2048-360-fmm-warm` | 2048 | 360 | 51.713 | 485.115 | 536.976 | 0.1564 | 12708 |
| `star-8192-180-TE-fmm-block8` | 8192 | 180 | 85.019 | 1360.111 | 1445.448 | 0.4153 | 13304 |
| `star-8192-180-compressed-packed-inverse` | 8192 | 180 | 40.211 | 3.996 | 44.425 | 0.7085 | — |
| `star-8192-180-compressed` | 8192 | 180 | 41.250 | 2.943 | 44.431 | 0.7016 | — |
| `star-8192-180-dense-disk-batch16` | 8192 | 180 | 46.167 | 13.036 | 59.604 | 1.1298 | — |
| `star-8192-180-dense-disk-batch256` | 8192 | 180 | 45.342 | 5.436 | 50.986 | 1.2593 | — |
| `star-8192-180-dense-memory-batch16` | 8192 | 180 | 44.439 | 16.570 | 61.406 | 2.1287 | — |
| `star-8192-180-dense` | 8192 | 180 | 45.211 | 5.386 | 50.831 | 2.2484 | — |
| `star-8192-180-fmm-batch8` | 8192 | 180 | 83.376 | 1823.728 | 1907.366 | 0.5283 | 18180 |
| `star-8192-180-fmm-block_gmres-tol0.0001` | 8192 | 180 | 87.327 | 785.876 | 873.438 | 0.4323 | 8160 |
| `star-8192-180-fmm-block_gmres-tol0.001` | 8192 | 180 | 86.938 | 1016.581 | 1103.783 | 0.4224 | 10520 |
| `star-8192-180-fmm-cold-tol0.001` | 8192 | 180 | 84.073 | 1256.824 | 1341.225 | 0.4116 | 7798 |
| `star-8192-180-fmm-recycle` | 8192 | 180 | 80.504 | 1381.112 | 1461.917 | 0.4047 | 8983 |
| `star-8192-180-fmm-rhs_qr` | 8192 | 180 | 83.912 | 1378.116 | 1462.265 | 0.4254 | 8987 |
| `star-8192-180-fmm` | 8192 | 180 | 78.845 | 1455.775 | 1534.941 | 0.4059 | 9430 |
| `star-8192-24-fmm-block-cadence4-tol0.0001-probe` | 8192 | 24 | 85.512 | 70.291 | 155.853 | 0.3913 | 768 |
| `star-8192-24-fmm-cold-tol0.0001-probe` | 8192 | 24 | 86.622 | 125.092 | 211.759 | 0.3551 | 813 |
| `star-8192-24-fmm-warm-probe` | 8192 | 24 | 84.888 | 196.706 | 281.642 | 0.3379 | 1312 |

A counts include true residual checks. For batched/block methods they sum
actual RHS column widths, not just traversal calls; these are not FLOP counts.

## Full complex-array comparisons

| Candidate | Dense reference | Field / reference peak | Max per-angle density L2 relative | RHS L2 relative | Passed |
|---|---|---:|---:|---:|---|
| `slot-1024-180-TE-fmm-block8` | `slot-1024-180-dense-cold` | 3.469e-13 | 9.220e-10 | 6.513e-17 | True |
| `slot-1024-180-TM-compressed` | `slot-1024-180-TM-dense` | 2.649e-13 | 3.479e-09 | 0.000e+00 | True |
| `slot-1024-180-TM-fmm-block8` | `slot-1024-180-TM-dense` | 1.479e-12 | 1.169e-09 | 0.000e+00 | True |
| `slot-1024-180-TM-fmm` | `slot-1024-180-TM-dense` | 9.775e-13 | 1.414e-09 | 0.000e+00 | True |
| `slot-1024-180-compressed-cold` | `slot-1024-180-dense-cold` | 2.266e-13 | 1.774e-11 | 0.000e+00 | True |
| `slot-1024-180-fmm-cold` | `slot-1024-180-dense-cold` | 7.226e-13 | 9.874e-10 | 0.000e+00 | True |
| `smoke-compressed` | `smoke-dense` | 4.462e-15 | 1.772e-13 | 0.000e+00 | True |
| `smoke-fmm` | `smoke-dense` | 9.169e-15 | 1.943e-13 | 0.000e+00 | True |
| `square-1024-180-compressed-cold` | `square-1024-180-dense-cold` | 2.247e-14 | 3.284e-13 | 0.000e+00 | True |
| `square-1024-180-fmm-cold` | `square-1024-180-dense-cold` | 1.419e-12 | 4.212e-12 | 0.000e+00 | True |
| `star-2048-180-TE-fmm-block8` | `star-2048-180-dense-cold` | 1.084e-12 | 2.393e-12 | 7.030e-17 | True |
| `star-2048-180-compressed-cold` | `star-2048-180-dense-cold` | 2.332e-12 | 1.896e-11 | 0.000e+00 | True |
| `star-2048-180-fmm-batch8` | `star-2048-180-dense-cold` | 1.043e-12 | 2.678e-12 | 0.000e+00 | True |
| `star-2048-180-fmm-cold` | `star-2048-180-dense-cold` | 1.621e-12 | 3.660e-12 | 0.000e+00 | True |
| `star-2048-180-fmm-lgmres_cold-inner80` | `star-2048-180-dense-cold` | 1.621e-12 | 3.628e-12 | 0.000e+00 | True |
| `star-2048-180-fmm-lgmres_cold` | `star-2048-180-dense-cold` | 1.178e-12 | 3.809e-12 | 0.000e+00 | True |
| `star-2048-180-fmm-packed-inverse` | `star-2048-180-dense-cold` | 1.843e-12 | 3.685e-12 | 0.000e+00 | True |
| `star-2048-180-fmm-recycle-inner80` | `star-2048-180-dense-cold` | 1.970e-12 | 3.005e-12 | 0.000e+00 | True |
| `star-2048-180-fmm-recycle` | `star-2048-180-dense-cold` | 1.226e-12 | 4.296e-12 | 0.000e+00 | True |
| `star-2048-180-fmm-rhs_qr` | `star-2048-180-dense-cold` | 1.186e-12 | 4.062e-12 | 7.030e-17 | True |
| `star-2048-180-fmm-warm` | `star-2048-180-dense-cold` | 1.976e-12 | 3.006e-12 | 0.000e+00 | True |
| `star-2048-180-full-compressed-cold` | `star-2048-180-full-dense-cold` | 2.809e-12 | 1.886e-11 | 0.000e+00 | True |
| `star-2048-180-full-fmm-recycle` | `star-2048-180-full-dense-cold` | 1.224e-12 | 4.301e-12 | 0.000e+00 | True |
| `star-2048-180-full-fmm-warm` | `star-2048-180-full-dense-cold` | 1.659e-12 | 3.605e-12 | 0.000e+00 | True |
| `star-2048-360-compressed-batch16` | `star-2048-360-dense-batch16` | 2.886e-12 | 1.896e-11 | 0.000e+00 | True |
| `star-2048-360-compressed-batch256` | `star-2048-360-dense-batch16` | 2.887e-12 | 1.895e-11 | 7.289e-17 | True |
| `star-2048-360-compressed-cold` | `star-2048-360-dense-batch16` | 2.886e-12 | 1.896e-11 | 7.289e-17 | True |
| `star-2048-360-dense-batch16` | `star-2048-360-dense-batch256` | 5.021e-15 | 1.740e-14 | 7.289e-17 | True |
| `star-2048-360-dense-batch256` | `star-2048-360-dense-batch16` | 5.021e-15 | 1.740e-14 | 7.289e-17 | True |
| `star-2048-360-fmm-cold` | `star-2048-360-dense-batch16` | 1.583e-12 | 4.514e-12 | 7.289e-17 | True |
| `star-2048-360-fmm-lgmres_cold` | `star-2048-360-dense-batch16` | 1.741e-12 | 4.406e-12 | 7.289e-17 | True |
| `star-2048-360-fmm-recycle` | `star-2048-360-dense-batch16` | 1.369e-12 | 4.587e-12 | 7.289e-17 | True |
| `star-2048-360-fmm-rhs_qr` | `star-2048-360-dense-batch16` | 1.862e-12 | 4.761e-12 | 7.289e-17 | True |
| `star-2048-360-fmm-warm` | `star-2048-360-dense-batch16` | 2.029e-12 | 3.034e-12 | 7.289e-17 | True |
| `star-8192-180-TE-fmm-block8` | `star-8192-180-dense-memory-batch16` | 9.679e-13 | 3.412e-12 | 6.667e-17 | True |
| `star-8192-180-compressed-packed-inverse` | `star-8192-180-dense-memory-batch16` | 3.448e-12 | 2.425e-11 | 6.667e-17 | True |
| `star-8192-180-compressed` | `star-8192-180-dense-memory-batch16` | 3.448e-12 | 2.425e-11 | 6.667e-17 | True |
| `star-8192-180-dense-disk-batch16` | `star-8192-180-dense-memory-batch16` | 0.000e+00 | 0.000e+00 | 0.000e+00 | True |
| `star-8192-180-dense-disk-batch256` | `star-8192-180-dense-memory-batch16` | 1.262e-14 | 1.610e-14 | 6.667e-17 | True |
| `star-8192-180-dense-memory-batch16` | `star-8192-180-dense` | 1.262e-14 | 1.610e-14 | 6.667e-17 | True |
| `star-8192-180-fmm-batch8` | `star-8192-180-dense-memory-batch16` | 1.277e-13 | 1.260e-12 | 6.667e-17 | True |
| `star-8192-180-fmm-block_gmres-tol0.0001` | `star-8192-180-dense-memory-batch16` | 7.460e-13 | 7.624e-12 | 6.667e-17 | True |
| `star-8192-180-fmm-block_gmres-tol0.001` | `star-8192-180-dense-memory-batch16` | 7.777e-13 | 5.231e-12 | 6.667e-17 | True |
| `star-8192-180-fmm-cold-tol0.001` | `star-8192-180-dense-memory-batch16` | 1.216e-13 | 1.018e-12 | 6.667e-17 | True |
| `star-8192-180-fmm-recycle` | `star-8192-180-dense-memory-batch16` | 1.028e-12 | 6.686e-12 | 6.667e-17 | True |
| `star-8192-180-fmm-rhs_qr` | `star-8192-180-dense-memory-batch16` | 1.289e-13 | 9.340e-13 | 6.667e-17 | True |
| `star-8192-180-fmm` | `star-8192-180-dense-memory-batch16` | 1.791e-13 | 9.563e-13 | 6.667e-17 | True |
| `star-8192-24-fmm-block-cadence4-tol0.0001-probe` | `star-8192-180-dense-memory-batch16` | 8.763e-14 | 4.744e-13 | 0.000e+00 | True |
| `star-8192-24-fmm-cold-tol0.0001-probe` | `star-8192-180-dense-memory-batch16` | 6.428e-14 | 7.818e-14 | 0.000e+00 | True |
| `star-8192-24-fmm-warm-probe` | `star-8192-180-dense-memory-batch16` | 9.006e-14 | 7.910e-13 | 0.000e+00 | True |

## Incident-load rank scans

These are RHS-only QR scans, not solves. They use production row-max scaling
and a 2e-15 relative Frobenius threshold. FMM solve-basis ranks use a different
equilibration and need not match these ranks exactly.

| Unknowns | k | Angles | Range | Rank | RHS reconstruction relative |
|---:|---:|---:|---|---:|---:|
| 2048 | 20 | 180 | [-90, 90) | 85 | 2.117e-15 |
| 2048 | 20 | 180 | [0, 360) | 119 | 2.158e-15 |
| 2048 | 20 | 360 | [0, 360) | 154 | 2.137e-15 |
| 8192 | 80 | 180 | [-90, 90) | 170 | 2.076e-15 |
| 8192 | 80 | 180 | [0, 360) | 180 | 8.426e-16 |
| 8192 | 80 | 360 | [0, 360) | 338 | 2.103e-15 |
| 32768 | 320 | 180 | [-90, 90) | 180 | 7.222e-16 |
| 32768 | 320 | 180 | [0, 360) | 180 | 7.214e-16 |
| 32768 | 320 | 360 | [0, 360) | 360 | 7.055e-16 |
| 65536 | 640 | 180 | [-90, 90) | 180 | 7.163e-16 |
| 65536 | 640 | 180 | [0, 360) | 180 | 7.156e-16 |
| 65536 | 640 | 360 | [0, 360) | 360 | 6.785e-16 |
| 32768 | 20 | 180 | [-90, 90) | 68 | 1.916e-15 |
| 32768 | 20 | 180 | [0, 360) | 105 | 1.843e-15 |
| 32768 | 20 | 360 | [0, 360) | 106 | 1.881e-15 |

## Rejected numerical runs

[]
