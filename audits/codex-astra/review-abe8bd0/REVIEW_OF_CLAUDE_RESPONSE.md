# Review of Claude’s Astra audit response

**Decision.** Accept Claude’s five findings. Keep the merged 2D solver and progress/Cancel changes for testing. Hold full-application distribution sign-off. Neither proposed patch is ready to merge as written. The next round should implement and test targeted fixes, starting with silently incorrect Line Expansion outputs.

GitHub confirms that `abe8bd0d6abb2c241a6f97fa31696ff09ac03c85` directly follows `bc19651`. It adds 43 audit files. All 528 production/resource files from `main` at `ed90b65` and all three earlier audit files match by Git object ID and mode. The force-added audit directory is expected. Both patches were applied only to disposable copies in this review. [Claude’s response](https://github.com/14cole/20261028_GRIM/blob/abe8bd0d6abb2c241a6f97fa31696ff09ac03c85/audits/claude-2026-11-26/astra-audit-response/RESPONSE_TO_CODEX.md)

## Line Expansion

Claude’s 26 tests reproduced unchanged. On released code, 18 failed and eight passed. All 26 passed on its trial. The shadowing wording should be corrected: in the GUI a valid multi-leaf occluder can cause the **job** to fail with a tuple/list error and no output file. The application stays usable. The offscreen GUI replay also reproduced the radian base being saved with 53.0% normalized complex-field error. The trial’s interval normalization addresses the reproduced shadow failures.

We extended the tests using real certified section solves and actual files. Each comparison uses maximum absolute complex-field difference divided by peak expected amplitude. The following figures describe these particular inputs. They are neither RCS-power errors nor estimates for the 2D solver.

| Input to the trial | Independent result | Required behavior |
|---|---|---|
| Compatible degree base | Adding the identical section doubled the stored field exactly. | Preserve the current result. |
| Degree-valued polar theta | Accepted without warning. Field error 324.1%. | Convert to canonical elevation or refuse before adding fields. Angle units alone cannot tell theta from elevation. |
| Opposite phase convention | Accepted without warning. Field error 99.2%. | Convert both complex representation and metadata coherently, or refuse. |
| Zero-field base with a declared old orientation and a new explicit orientation | First addition exactly matched the explicit orientation. File kept both the old request and new line provenance. Next implicit addition used the old orientation and missed the expected doubled field by 70.9%. Restating the orientation was exact. | Resolve conflicts before adding, and persist an unambiguous effective orientation that the next reader actually uses. For an existing nonzero body field, validate whether the requested combination is meaningful before accepting an override. |
| Two individually accepted input sweeps | 35,901 azimuths × 18,001 elevations = 646,253,901 looks. A single four-component complex128 array would require 38.5 GiB. We counted dimensions only. | Validate the combined working set before creating look arrays. Include explicit lists as well as sweep notation. |

The orientation failure also reproduced when a BoR-profile loader supplied default zeros in the absence of a declared orientation. The trial successfully covers its tested radian, VH/HV and simple orientation cases, but it leaves known paths to silent errors.

**Cancellation.** The current GUI tells the user that cancel waits for the section. The underlying certified solver accepts an `abort_event`; the Line Expansion worker did not pass its event through. We also injected cancellation deterministically just after the real writer finished staging the file and before the rename. Both release and trial emitted `finished` and replaced the previous output despite the already-set event. A pre-canceled control preserved the old bytes, and an uncanceled control succeeded. Use the same cancellation signal through section solves and define the cancellation cutoff at publication. Test the publication boundary independently of thread timing. This finding concerns the Line Expansion tab. The separate Solver-tab Cancel fix remains supported.

**Implementation scope.** Address LE-01 through LE-04 and LE-09 at the file boundary, plus cancellation (LE-05), combined input size (LE-06) and help text (LE-08). For LE-07, make the certified section-solve policy explicit. Automatically inheriting unrelated Solver-tab settings would be a separate product choice. Check the shared Assembly shadow caller and reopen saved outputs for each regression.

## Linux RAM admission

I accept Claude’s extension to cgroup v1. I recomputed ten saved real-run records from byte counters. Against the intended 90% budget, the ordinary v1 container was over-admitted by 3.69 GiB and the 1 GiB child by 12.53 GiB. These are *excesses over the correctly reserved budget*, rather than amounts allocated or an observed OOM. The real nested v1 cases are Claude’s runs. Our new live check was a read-only cgroup v2 root control. Both public backends ran on the trial and reproduced all 720 reference complex samples for the 512-panel magnetic dielectric cylinder.

Claude’s synthetic suite also reproduced: nine of fourteen baseline budgets disagreed with its expected values, and the trial matched all fourteen. Three independent fixtures change the repair recommendation.

- With 4 GiB available in the process's own group, the trial correctly gave a 3.6 GiB solve budget. Adding an unrelated sibling cgroup bind mount reduced the same process's budget to 0.1125 GiB. Consider only mounts and ancestors that can constrain this process. Include namespace-root and multiple-mount cases.
- An unrelated mount name with non-UTF-8 bytes raised `UnicodeDecodeError` during the trial probe. Linux paths can contain these bytes. Discovery should tolerate them.
- If a group's usage counter is unreadable, the group's remaining bytes are unknown. In a 6 GiB group actually using 2 GiB, subtracting only the current process's 0.25 GiB RSS gave 5.75 GiB of apparent headroom instead of 4 GiB. A finite limit alone is not proof of available bytes. Document fallback uncertainty and test behavior with sibling usage.

The HPC scheduler also needs attention. On a synthetic visible 512 MiB root cap its existing capacity probe reported 32 GiB of host capacity. Share hierarchy discovery, but preserve the distinct meanings of **total capacity** (scheduler) and **currently remaining bytes** (solve admission). The trial touches only the solver. No scheduler job or native Windows memory run was performed.

## Packaging and native diagnostics

The threadpoolctl notice omission is confirmed in a fresh native wheel and sdist. The release source ZIP contains it. Claude also correctly found that the dataclasses notice is absent from those Python packages. History shows it accompanied the old Python backport, removed at `43b92b0`. The current runtime imports standard-library dataclasses; the HPC snapshot still lists the notice. Preserve both shipped notices as package data. The two-notice trial restored byte-identical texts in the rebuilt portable wheel, sdist and source ZIP. This treats the dataclasses notice as packaging consistency, without claiming a present backport dependency. [Historical runtime](https://github.com/14cole/20261028_GRIM/blob/7a853d8/tools/GHOST/ghost_backend/execution/runtime.py#L6-L10)

With the healthy libraries and with just the 2D near library removed, the speed diagnostic returned seven OK rows. All three 384-panel solves in each state completed with identical fields and empty warnings. The test does not price the cost of losing the near kernel. Claude’s table-path trace does identify SciPy versus native table evaluation. The missing user-facing warning and missing near/far distinction are the specific gaps. The wheel also omits the checkout's diagnostic script and manifests. A supported wheel install needs an accessible diagnostic or accurate instructions for that format.

Claude’s archived Linux logs support a child process dying with SIGBUS on a partly copied library. I did not independently run a damaged binary. All eight tracked binaries matched their manifests. In a fresh supported `--native --no-openmp` build, the BoR shared library had a different hash from the checkout while matching the wheel’s own RECORD and generated manifest and exporting every required symbol. Verify stock binaries against the identity recorded for **that artifact** before loading, and define how legitimate local rebuilds are recognized. Test all four library loaders and the export-level capability checks. A checkout-only hash allowlist would reject a supported build.

## Release decision and review order

1. Repair and independently test Line Expansion output conventions, orientation persistence, reciprocal channels and shadowing first. Include cancellation at both solve and publication boundaries, and grid preflight.
2. Fix package data and native diagnostics for the actual shipping format. Revise both Linux memory probes and run matching controls plus actual Dense/Compressed jobs.
3. Run the intended distribution on the representative 32 GB Windows desktop, including native loading, completion, memory, cancellation, restart, export readback, and default shadowing on a BoR base. Machine access and a representative model remain open. Current solver and GUI conclusions stay scoped to their validated fixtures.

These findings give the next implementer concrete failing tests. Another broad backend benchmark would not settle these defects. [Replay instructions and evidence](CHECKS.zip)
