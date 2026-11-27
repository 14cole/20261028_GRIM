# Plan, written before any measurement and before opening Codex's report or evidence

Read so far: `HANDOFF_FOR_CLAUDE.md` only. Not opened: `REPORT.md`, the evidence archive.
One solve has been run, to check my predicted amplitude convention (PEC 256-gon, 3 GHz):
the prediction B = -4jP matched both polarizations to 3e-4 with no fitted constant.

Code under test: `ed90b65`, from `git archive` (my working branch carries unrelated
Line Expansion changes, so the solver is never imported from it).

## Reference
`reference.py`: cylindrical-wave series for a PEC cylinder and a PEC core with a
homogeneous coating, TM and TE, with the monostatic translation phase
exp(2jk khat.r0). Its self-checks use no solver: vacuum coating equals the bare
core, lossless partial waves are unitary, lossy ones are sub-unitary, and the
PEC high-frequency limit is pi*a.

## Metric
E = max over angles |B_ghost - B_ref| / max over angles |B_ref|, per polarization,
on complex amplitudes. Dense against Compressed on the identical mesh uses the
same form with Dense as the reference, plus the relative 2-norm.

## A. Accuracy on specified meshes
360 angles (0..359 deg), cylinder centre translated to (0.031, -0.017) m.
Boundaries are regular inscribed polygons, one panel per side; refinement doubles
the outer side count: 128, 256, 512, 1024 (inner ring in proportion to its radius).

| Fixture | Core a (m) | Outer b (m) | eps | mu | GHz |
|---|---|---|---|---|---|
| pec | - | 0.050 | - | - | 3, 10 |
| coat | 0.040 | 0.050 | 2.8-0.06j | 1 | 3, 10 |
| coat-magnetic | 0.040 | 0.050 | 4-0.5j | 1.5-0.3j | 6 |
| coat-thick | 0.030 | 0.060 | 2.8-0.06j | 1 | 6 |

Each mesh is solved with Dense and with Compressed. I record the backend that
actually ran, panels, unknowns and the quality gate. A refusal is a result.

## B. What certification establishes
Shipped Automatic workflow, standard target, automatic backend, wavelength sizing
(N = 0). The same circle drawn as inscribed polygons of 16, 32, 64 and 360 sides,
for the bare PEC cylinder and the coated cylinder at 6 GHz. I record the published
mesh, the certified flag, the reported base-to-fine change, and E against the
ideal circle. Prediction: the certificate describes convergence on the drawn
polygon, so a coarse polygon will certify with an error against the circle far
above its reported change.

## C. Time and peak RAM
Fresh process per job; both polarizations; RHS compression off; batch 256; same
mesh for both backends. Peak RSS from the child's VmHWM and from wait4.
Coated cylinder (a = 0.10, b = 0.12 m, eps 2.8-0.06j) at 10 GHz, sized by side
count to roughly 3k, 6k and 12k unknowns, so the analytic error is also known at
scale. 180 and 360 angles. One thread for the two smaller sizes with three
repeats; the largest with the thread count and repeats the wall time allows,
stated in the results. If Dense is refused for memory at the largest size, that
is recorded.

## Hardware
This container: 4 vCPU, 15 GiB RAM (13.35 GiB cgroup limit), Linux. No Windows
machine is attached to this session, so Windows capacity stays open.
