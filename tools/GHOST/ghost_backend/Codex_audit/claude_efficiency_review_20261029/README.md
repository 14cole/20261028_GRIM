# Review of Claude's resource-efficiency audit — 29 October 2026

Reviewed [Claude's report](../../Claude_audit/review_of_codex_resource_efficiency.md) against `743d6391dfa18a7b71c369e4553d5d7b39194155`, the pushed implementation, saved trial evidence and existing impedance/material conventions. The objective remains reliable throughput and accurate resource estimates; 90% RAM utilization is a soft goal.

**Retain the implementation and existing automatic CPU defaults.** Claude's acceptance of the fallback-sizing fix is supported. No new reproduced production defect was found in this review. The proposed impedance-boundary study is promising, but its units, physical validation and projected runtime need qualification before it becomes an implementation recommendation.

## 1. Impedance input must be in ohms

For the supplied constant material properties, epsilon = 101.19−11.88j and mu = 3.45−3.47j, direct calculation gives:

| Quantity at 15 GHz | Verified value |
|---|---:|
| Complex refractive index | 20.0802−9.76375j |
| Phase wavelength in the material | 0.9953 mm |
| Field-amplitude decay length | 0.3258 mm |
| Normalized surface impedance, Zs/Z0 | 0.206916−0.0721967j |
| Surface impedance, Zs | **77.9516−27.1987j ohms** |

Claude labels the normalized value correctly in its table, but later suggests applying that value directly to the contour without stating GHOST's required conversion. GHOST's inline IBC entries use **ohms**, not Zs/Z0. `MaterialLibrary.from_entries` preserves the supplied complex value; `_surface_robin_alpha` explicitly divides or multiplies by the medium impedance. Existing cylinder tests use inputs such as 55−12j ohms.

A future IBC experiment must therefore use the ohmic value above, with the existing passive `exp(+j*omega*t)` convention. It must change the closed contour from TYPE 3 (bulk material/air) to TYPE 2 (opaque IBC), assign the IBC flag, and remove the bulk-region assignment for that contour. Merely adding an IBC row to the existing TYPE 3 interface is not the same formulation. This review only checks an in-memory material definition; it does not change a production model.

## 2. A promising approximation, not an equivalent faster solver

The large refractive index and short decay length support investigating a Leontovich boundary. This approximation replaces the penetrable material with a surface law and excludes its interior. The high-index, short-penetration rationale agrees with [COMSOL's RF impedance-boundary documentation](https://doc.comsol.com/6.3/doc/com.comsol.help.rf/rf_ug_radio_frequency.07.032.html).

That does not establish its error for this dogleg. The contour has sharp concave and convex corners, where the local smooth-surface argument is weakest, and grazing incidence or cavity scattering can make small boundary-law errors important. A finite six-inch material thickness is reassuring for attenuation through the body, but does not resolve corner accuracy. COMSOL's illustrative skin-depth modelling guidance explicitly scopes its smooth-surface comparison away from sharp corners: [conductor meshing and modelling guidance](https://www.comsol.com/support/learning-center/article/understanding-the-options-for-meshing-and-geometric-modeling-of-conductors-in-electromagnetic-fields-81171).

Agreement at 2–3 GHz would be useful evidence, not automatic certification at 15 GHz. Electrical size, corner diffraction and angular scattering change with frequency. For a real dispersive material, epsilon, mu and the derived impedance must also be evaluated consistently at each frequency. The synthetic constants here do not establish real broadband material behavior.

The existing solver's residual and mesh-convergence gates certify a solution of the chosen model. They do not establish that the IBC model reproduces the original bulk-material physics. Do not silently substitute it for the user's material model as a memory optimization.

## 3. Mesh and runtime estimates need correction

The saved dogleg contour has a perimeter of **564 inches = 14.3256 m**, not roughly 9 m. The code's controlling bulk mesh wavelength is about **0.8951 mm** at 15 GHz, distinct from the 0.9953 mm phase wavelength in the table. With the saved `N=-20` density, the ungraded reference panel counts calculated by the actual counting function are:

| Frequency | Bulk controlling wavelength | Ungraded reference panels |
|---|---:|---:|
| 2 GHz | 6.7133 mm | 42,683 |
| 3 GHz | 4.4756 mm | 64,024 |
| 15 GHz | 0.8951 mm | 320,091 |

These are counts before grading and certification refinements, not completed meshes or memory measurements. They explain why 100,000 panels is restrictive at 15 GHz. They also show why a lower-frequency full-material comparison is not automatically a cheap or comfortably fitting run.

For the correctly converted IBC, the current mesh-control routine returns the free-space wavelength and no counted slow bound surface wave for this impedance. That supports a potentially much smaller mesh. It does **not** establish 10,500 final nodes or a one-minute runtime: an impedance operator differs from PEC, and ranks, conditioning and adaptive convergence still need measurement.

The stress trial hit the configured panel limit before matrix assembly, not before using any RAM. Its measured peak tree RSS was approximately 0.388 GiB. We still do not know the full bulk solve's peak memory. Claude's statement that the case probably does not need more RAM should be read as a proposed alternative model, not a demonstrated resource requirement of the original model.

## 4. Automatic CPU profile: keep the measured result scoped

The 21.43% improvement is well supported for the repeated 15 GHz ordinary-inlet profile comparison on this eight-core host: 117.70 versus 149.81 seconds. Automatic execution was already the default, and its fields differed from the reference by at most 4.13e-16 relative error. Use automatic settings as the baseline for future production-representative studies.

It is not established that every earlier audit time understates real-world speed by 20%. Other geometries, materials and stages can scale differently, and prior calibration included both two-worker and eight-worker cases. Alternating order and close repeats strengthen this comparison; they do not mathematically exclude every form of host drift. Explicit four-worker controls remain useful when a study is specifically about CPU scaling.

## 5. Suggested double-counting issue is not yet a counterexample

Claude's note about an already resident opposite-polarization operator is a reasonable scenario to investigate, but it does not establish duplicate accounting. The tile forecast prices one resident polarization and treats its partner as disk storage. A **different** operator still resident in RAM may therefore need the extra allowance. Also, `compressed/runtime.py:native` takes and reloads a matching cached partner before reaching the fallback-building path.

To justify changing credits, a regression must show the same identifiable allocation represented twice in the applicable storage and live-residency terms, with its lifetime traced through the actual fallback path. Do not subtract another operator's bytes from whole-process RSS simply because it belongs to another polarization. No such production counterexample was reproduced in this review, and no credit or allowance was changed.

## Suggested next order

1. Keep `743d639` and the automatic CPU profile. No pagefile, utilization target or active-worker allowance change is indicated.
2. If this magnetic material is an intended workload, make the next task an explicitly labelled **bulk-versus-IBC modelling study**, not an automatic production substitution. Establish acceptable error measures for both polarizations and the relevant angular/frequency range before declaring equivalence. Use absolute or normalized field/RCS measures alongside dB differences so deep nulls do not distort the comparison.
3. Start with the existing full-material and impedance-cylinder reference functions at relevant frequencies to check units, signs and smooth-boundary approximation error. Then use bounded full-material versus IBC comparisons on suitable concave contours, including corner/rounding sensitivity. Lower-frequency dogleg comparisons are one component, not sufficient 15 GHz qualification by themselves.
4. For faster moderate-dielectric solves without changing the physical model, the measured assembly and independent P2/P3 certification work remain useful optimization targets. Preserve the actual certification comparison while evaluating reuse or kernel changes; do not omit P3 merely to improve timing.

## Verification scope

[verification.json](verification.json), reproducible with [verify_review.py](verify_review.py), checks ten validated source/test hashes, the saved 624-test/114-subtest record and six certified numerical runs. It also computes the material scales, contour perimeter, raw panel counts and IBC unit conversion using the existing code. This review ran no new solver workloads or regression suite, changed no production code or geometry, and committed/pushed nothing. The original Claude report and all trial evidence are preserved.
