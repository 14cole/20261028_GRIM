# Independent review of GHOST backend accuracy, solve time, and peak RAM

Please review the shipped GHOST 2-D Dense and Compressed backends at `ed90b65ff89826274adacae01bcfbafe143e9819` in `14cole/20261028_GRIM`. The user's priority is reliable complex fields and practical turnaround on a 32 GB desktop. Typical studies use 2–15 GHz, 180–360 distinct monostatic incident angles, and may contain PEC and dielectric layers. This branch adds review material to the tested revision.

## Independent checks first

Write down your independent fixture, reference calculation and error metric before reading the measured values in REPORT.md or inspecting the result arrays. Save your independently generated complex fields and environment details before comparing. Three questions drive this review.

1. **How accurately do both backends reproduce the physics?** Use an analytical 2-D cylinder reference independent of the supplied reference code. Include both polarizations and a translated cylinder to test phase around the angular sweep. A PEC core with a dielectric coating is the highest-value case. Vary a material, radius or frequency and refine the boundary discretization. Report the maximum complex-field difference normalized to the peak reference magnitude and the change with refinement. Compare Dense and Compressed on the identical mesh as a separate check.
2. **What does mesh certification establish?** Use the shipped Automatic workflow and its standard accuracy target. Compare a curved boundary represented with two different input polygon resolutions. Record the published mesh, base-to-fine change, and error against the ideal analytical geometry. Does the certificate accurately describe what converged?
3. **When does Compressed earn its memory savings?** Time the 180- and 360-incident-angle sweeps in fresh processes with the same mesh, polarizations, solver gates, thread count and batch size. Record actual backend, panels, unknowns, wall time, peak process memory, repeat spread and full complex fields. For scaling, one larger mixed-material case would add more information than further repeats of the small ellipse. Use a representative model on a 32 GB Windows desktop if available. Otherwise identify the hardware and keep Windows capacity as an open question.

## Then cross-check the evidence

Read the report, extract the archive, verify SHA256SUMS, and follow REPRODUCE.md inside. The evidence includes all 24 fixed-mesh cylinder jobs, two Automatic mesh-certification controls, eight timed ellipse jobs and a separate refined-mesh ellipse solve. The ellipse timing comparison uses both polarizations and one assembly and BLAS thread. It measures fresh-worker peak RSS on Linux. On Windows, record peak working set and peak private commit separately. Keep historical two-incidence results separate from full monostatic sweeps. [Codex report](./REPORT.md) · [Scripts, arrays, metadata and replay instructions](./GHOST-backend-evidence.zip)

Please return a review with your commit, hardware, independent calculations, raw arrays and replay results. For each material disagreement, identify the fixture, polarization, angle and metric, or the configuration and run spread for a performance discrepancy. Conclude with the backend and mesh guidance supported by the measurements and the highest-value remaining test for the user's desktop.
