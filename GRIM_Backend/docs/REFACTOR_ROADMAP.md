# GRIM refactor roadmap

GRIM's most useful larger refactors would give assembly calculations, background jobs, and solver support code clearer ownership. Keep the existing GRIM, GHOST, and FREDDY package boundaries. Begin with the assembly tree calculation boundary, where a plain data snapshot already provides a migration path, after preserving and baselining the regression tests.

This assessment describes the working checkout on October 24, 2026. The proposed modules below do not yet exist. Priorities reflect dependency structure and behavior that must be preserved, rather than file size alone. Runtime performance improvements require measurement.

## Priorities

| Order | Refactor | Expected benefit | Migration risk |
| --- | --- | --- | --- |
| Prerequisite | Preserve tests and establish a baseline | Makes regressions reproducible from a fresh checkout | Low for tracking; investigate existing failures separately |
| 1 | Separate assembly calculation from the Qt tree | Makes physical combination rules independently testable and usable from scripts | Medium |
| 2 | Give dataset jobs explicit request and lifetime ownership | Makes cancellation, one-time storage choices, and result publication easier to reason about | Medium to high |
| 3 | Separate GHOST assembly contracts, calculation, and publication | Makes data integrity rules and output transactions independently reviewable | Medium to high |
| 4 | Extract assembly readiness decisions and component views | Reduces coupling between validation state, labels, and buttons | Medium |
| 5 | Complete FREDDY's separation of analysis from widgets | Makes analysis reusable and reduces the main window's responsibilities | Medium |
| 6 | Untangle BoR support dependencies before splitting solver families | Makes numerical changes more local and clarifies resource ownership | High for numerical extraction; lower for isolated policy moves |
| 7 | Move plotting controllers onto their existing canvas contexts | Reduces dependence on the entire application window | Medium; defer while active ISAR changes settle |

## Preserve the regression baseline

There are 450 local `test_*.py` files in the main GRIM, GHOST, and FREDDY test directories, but no tracked test files in the Git inventory. The root `.gitignore` rule `tests/` excludes these directories. Review and track test source, configuration, and necessary small fixtures. Keep generated outputs and large external reference datasets separate. Release packaging already excludes tests through `release_validation.py`; Git tracking and release inclusion are separate decisions.

Establish one documented command for fast regression checks and a separate command for longer numerical qualification. Run the relevant suites before each extraction and preserve their results. A failing baseline should be understood before using that suite to judge a refactor. The test names below identify existing candidates; they do not certify that those suites currently pass.

Current local edits include ISAR and exploratory GHOST work. Keep refactor changes separate from those changes and review the working state before starting each implementation.

## Separate assembly calculation from the Qt tree

[assembly/tree.py](../assembly/tree.py) combines tree widgets, drag and drop, document serialization, physical response validation, axis alignment, and numerical assembly. It contains roughly 4,000 lines. `build_assembly_grid` accepts a `QTreeWidgetItem` and reads Qt roles to decide how to combine responses. `_BuildNode` already captures data on the GUI thread, but emulates the Qt item interface and still uses Qt constants.

Proposed ownership:

| Module | Responsibility |
| --- | --- |
| `assembly/tree.py` | Tree widgets, selection, drag and drop, and capture of build requests |
| `assembly/response_model.py` | Plain response nodes with name, inclusion, combination mode, grid, and children |
| `assembly/response_semantics.py` | Response identities, physical compatibility, provenance retention, and duplicate-body/component checks |
| `assembly/response_build.py` | Axis alignment, coherent/incoherent combination, cancellation, and build reports |
| `assembly/response_document.py` | Serialization of plain document snapshots and document version handling |

Keep these response-tree types distinct from the existing feature-placement form model in `assembly/model.py`. They represent different workflows.

Start by defining a plain response-node snapshot and a GUI adapter. Move the calculation and its required semantics together so they do not import `tree.py`. Retain `tree.build_assembly_grid` temporarily as a compatibility adapter. Move document serialization in a later change, preserving the existing on-disk format.

The snapshot should capture structure, settings, and dataset identity. Do not deep-copy every large sample array: establish how referenced datasets stay alive and how mutation is prevented or detected during a build. A frozen wrapper alone does not make NumPy arrays immutable.

Acceptance criteria:

- The calculation imports and executes with PySide6 unavailable. Existing feature-recipe headless tests cover a different path and do not establish this property for the response tree.
- Field addition, power addition, mixed branches, axis intersection/interpolation, and metadata propagation retain their results and diagnostics.
- Hiding preview geometry does not change physics; disabling response membership does.
- Duplicate bodies and feature components remain rejected, including after save/load and tree duplication.
- Cancellation publishes no partial dataset, and RAM/Auto/Disk policies remain effective.

Existing test starting points: `test_assembly_tree_safety.py`, `test_assembly_visibility.py`, `test_assembly_interference.py`, `test_assembly_review_implementation.py`, and `test_assembly_headless.py` under `GRIM_Backend/tests`.

An adjacent improvement deserves a separate change: `_phase_identically_zero` converts whole `grid.power` and `grid.phase` views with `np.asarray` and allocates a whole-grid mask. Replace that advisory scan with bounded blocks and an early exit, preserving its treatment of nonfinite power and phase. Verify memory behavior on a large disk-backed or derived-view dataset. This is a concrete allocation concern, not a measured performance result.

## Give dataset jobs explicit ownership

[ui/dataset_actions.py](../ui/dataset_actions.py) has approximately 6,400 lines and 135 methods in `DatasetOpsMixin`. It coordinates imports, table selection, numerical actions, exports, progress, cancellation, and publication. Numerical workers already live in [execution/dataset_jobs.py](../execution/dataset_jobs.py), so the next step is to extract coordination rather than duplicate those workers.

The clearest coupling is `_outermost_action_code` and `_action_still_running`: they inspect Python stack frames to determine whether a pending one-time storage override still belongs to the action that accepted it. The window also holds pending callbacks, import queues, unit confirmations, and operation-specific fields.

Introduce an explicit `DatasetJobRequest` containing captured dataset IDs/references, parameters, storage options, recorder inputs, and a cancellation token. A `DatasetJobController` owns the active worker/thread and its lifecycle. A separate import coordinator owns queued imports and requests for table mappings or unit declarations. The window supplies prompts and presents results.

Pass a one-time storage decision directly into the request it belongs to. A declined, invalid, or superseded request then cannot accidentally carry that decision into a later action. Use an operation ID for completion routing; release unpublished results when the originating request is no longer valid.

Migrate one action, such as Offset, through capture, execution, and publication first. Then move import coordination and the other actions in small groups. Keep current worker implementations and Qt signal wiring until the controller path is proven. Avoid a new universal job framework spanning GRIM and both standalone tools in this first pass.

Acceptance criteria include nested modal interactions, two attempted launches, cancellation before and during work, closing the window, delayed completion, selection changes after launch, and failures during result publication. Recording must use launch-time identities and parameters. Results and worker resources must be released exactly once.

Existing test starting points: `test_gui_dataset_workflows.py`, `test_load_memory_controls.py`, `test_action_recipes.py`, `test_bounded_dataset_operations.py`, and `test_dataset_button_regressions.py` under `GRIM_Backend/tests`. Add focused coverage for request-owned storage choices and stale completions where the current tests do not cover them.

After that boundary is established, separate table/catalog presentation, import/export actions, and operation dialogs. Moving the existing methods into several mixins without reducing their access to window state would mostly relocate the complexity.

## Separate GHOST assembly contracts and publication

[GHOST assembly/fields.py](../../tools/GHOST/ghost_backend/assembly/fields.py) has roughly 5,800 lines. It handles native field interpretation, body artifacts, point and line responses, capacity estimates, output locking, staging, and publication. [assembly/workflow.py](../../tools/GHOST/ghost_backend/assembly/workflow.py) has roughly 4,700 lines spanning request types, placement CSVs, manifests, surface binding, preparation, and execution.

Existing `contracts.py` and `preparation.py` extractions still import helpers and types back from `workflow.py`. Some imports even obtain `math`, `np`, and typing names from the orchestration module. This is concrete evidence that the dependency boundary needs work, even though local imports can make the current arrangement run successfully.

Proposed modules within `ghost_backend/assembly`:

- `requests.py`: request, plan, and preview data types, including versioned contracts.
- `placements.py`: CSV parsing, identifiers, and preparation of point/line placement records.
- `manifests.py`: manifest parsing, validation evidence, response identities, and support rules.
- `surface_binding.py`: binding identity, validation, and sidecar persistence.
- `publication.py`: locks, staging, source rechecks, rollback, and publication of related outputs.
- `capacity.py`: resource estimates and admission checks for feature assembly.

Within `ghost_backend/io`, place native field decoding and convention checks behind a focused service used by both assembly and viewer/export code. Keep physical response calculations in assembly modules. Let `workflow.py` coordinate these services and retain necessary public compatibility exports.

Do not start by rewriting the entire 566-line `add_features_to_monostatic_grim`. First extract the publication transaction with its current guarantees, then move capacity checks and native interpretation, then separate calculation stages. Preserve the timing of capacity rechecks under the output lock and the source-fingerprint checks immediately before publication. Preserve existing platform behavior for atomic links and filesystem failures.

Acceptance criteria include changed inputs after validation, destination collisions, cancellation during staging, insufficient disk capacity, failure publishing one of multiple outputs, lock contention, and cleanup after failure. Existing outputs must retain the guarantees of the current implementation. Numerical field scaling, channel order, complex values, units, and provenance must remain equivalent.

Existing GHOST test starting points: `test_feature_job_control.py`, `test_feature_capacity.py`, `test_feature_production_contracts.py`, `test_feature_workflow.py`, `test_assembly_equivalence.py`, and `test_assembly_performance_fixes.py`.

Keep GHOST independent of GRIM. Similar rules across their packages may warrant contract tests with shared fixtures; they do not automatically justify importing the application into the solver.

## Extract assembly readiness and component views

[assembly/panel.py](../assembly/panel.py) has a 1,166-line `_build_ui` and a 577-line `_update_workflow_readiness`. Readiness currently reads form values, examines current requirements and mappings, chooses the next-step explanation, enables actions, and changes presentation styling.

Introduce a plain `ReadinessSnapshot` assembled from form values, current source evidence, prepared-plan identity, warning acknowledgments, and job state. A pure evaluator returns a `ReadinessResult` containing allowed actions, reasons, warnings, and the recommended next step. The panel renders that result. Keep filesystem discovery and source hashing outside the pure evaluator; a cheap refresh must not silently become an expensive validation.

Keep backend validation authoritative at execution time. A GUI readiness result is guidance based on a snapshot, not permission to bypass validation when inputs change.

Then extract body, placement, response-mapping, and build sections into owned widgets with explicit inputs and signals. Preserve their public interactions while removing imports of widget helpers from the main panel. For example, `vehicle_ui.py` currently imports `_DisclosureSection` from `panel.py`; a shared local widget module would remove that backward dependency.

Also move recipe constants and path normalization into focused lower-level modules. `recipe.py` currently lazily imports helpers from `model.py`, which imports recipe functionality back. `assembly/workflow.py` retrieves recipe/path helpers through `panel.py`; it should use the modules that own those helpers directly.

Acceptance criteria: identical action availability and explanations for incomplete forms, stale inputs, missing mappings, invalid units, rejected output aliases, unreviewed warnings, open editors, active jobs, and errors while pulling form values. Existing tests include `test_feature_assembly_panel.py`, `test_feature_composer.py`, `test_assembly_authoring_updates.py`, and `test_assembly_clear_workspace.py`.

## Complete FREDDY analysis separation

[FREDDY ibc/ui.py](../../tools/FREDDY/ibc/ui.py) has roughly 5,500 lines. It already uses project, analysis, inverse-workflow, and inverse-results components. `MixSearchRequest` and `run_mix_search` demonstrate an existing request/service pattern worth extending.

The remaining `_compute_heatmap_data` and `_compute_thickness_data` methods perform analysis inside the window class; `_compute_heatmap_data` can also read frequency widgets when its `freqs` argument is absent. Move these calculations into Qt-free analysis services with explicit frequencies, angles, layers, uncertainty, and output options. Capture values on the UI thread before execution.

Preserve both the vectorized and fallback calculation paths unless the supported runtime policy is deliberately changed. Move result summaries next, followed by material-mix view/controller ownership. Continue using the existing inverse and mix search services rather than creating another numerical implementation.

Replace window-bound numerical callbacks with explicit services where they do not need UI state. Preserve the current input-revision check that prevents using material-mix results after inputs change. Retain cancellation, checkpoint/resume, and export provenance behavior.

Acceptance criteria include GUI/service result equivalence, frequency coverage validation, anisotropic layers, sheet layers, uncertainty corners, interrupted searches, resume without repeating completed scores, and project portability. Existing FREDDY starting points include `test_physics_and_io.py`, `test_inverse_workflow.py`, `test_inverse_results.py`, and `test_project_portability.py`. Add direct tests for the newly isolated analysis services.

## Untangle BoR dependencies before dividing solver families

[GHOST bor/solver.py](../../tools/GHOST/ghost_backend/bor/solver.py) contains approximately 7,500 lines. It mixes resource planning, constrained bases, near quadrature, angular caches, modal convergence, conductor operators, cross-surface operators, and material-family orchestration.

Several support modules depend back on it: `factor.py` imports numerical acceptance thresholds, `geometry.py` imports segment intersection, `tiled.py` imports pair-block generation, and `near_parallel.py` imports near-integration helpers. `preparation.py` imports solver classes. These local imports are not proof of a runtime failure, but they constrain clean extraction.

Start with small lower-level ownership changes:

1. Put shared numerical acceptance thresholds in a focused policy module.
2. Put geometry predicates and pair iteration in modules that do not import solver orchestration.
3. Move resource estimates and worker planning together with their explicit inputs. Retain existing option scopes and checkpoint propagation.
4. Move near-integration primitives once their data and cache dependencies are explicit.

Only then consider separating conductor operators, cross-surface operators, mode sweeping, and material-family solve orchestration. Retain public `solve_bor*` entry points through a compatibility facade. Avoid forcing PEC, dielectric, partial-coating, and multiregion equations into one generalized abstraction merely because some control flow looks similar.

Windows worker startup, serialized/imported function locations, cancellation, cache keys, memory limits, convergence thresholds, and operation ordering all need attention during these moves. Tests that patch names in `solver.py` may need to target the new owning module; a re-export does not automatically preserve monkeypatch behavior.

Existing GHOST starting points include `test_bor_physics_regression.py`, `test_bor_memory_planning.py`, `test_bor_modal_preparation.py`, `test_bor_touching_pairs.py`, `test_bor_compute_reuse.py`, and `test_bor_capability_acceptance.py`. Use appropriate PEC, dielectric, coating, junction, and multiregion reference cases. Compare complex fields and existing diagnostics, not just final dB plots. Measure peak memory and time separately if resource behavior changes.

## Move plot controllers onto existing contexts

[plotting/actions.py](../plotting/actions.py) has approximately 3,400 lines and 153 methods. [plotting/session.py](../plotting/session.py) already gives each canvas resource ownership and cancellation, while a compatibility facade exposes context properties on the window. Shared request preparation already exists in `plotting/requests.py`.

Continue that architecture by giving plotting controllers an explicit canvas context and session instead of the full window. Start with artist cleanup and native-sample resource lifetime, then move render orchestration and interaction ownership. Preserve the current one-running/one-pending request policy and generation checks in the existing job service.

Defer changes to ISAR internals until the current working changes are stable. Existing `test_plot_preparation_architecture.py` covers tab ownership, late-result rejection, cancellation, marker state, and selected-resource lifetimes; use it to protect this extraction rather than replacing the established design.

## Dependency rules and incremental delivery

Useful boundary checks should enforce a few explicit rules:

- Response-building and readiness modules must import without Qt.
- GHOST computational modules must work without importing GRIM.
- Solver support modules must not import the orchestration facade once their dependencies have been moved.
- Worker calculations must receive captured inputs and publish through the owning controller.
- Native format, physical units, metadata retention, and release packaging remain compatibility contracts.

A static import scan includes intentional local and conditional imports. Use it to find dependencies to inspect, not as a list of broken modules. Enforce selected boundaries with focused import tests rather than banning every import cycle across the repository.

Deliver each refactor as reviewable changes: establish behavior, introduce the new boundary, migrate callers, and remove obsolete internals only after checking remaining references. Keep behavior fixes and numerical changes separate from moves where practical. Document temporary compatibility exports with their consumers and removal criteria.

The first implementation milestone should be a Qt-free response builder with the old GUI entry point delegating to it. Completion means the engine runs from a script, the GUI retains existing behavior, and the relevant regression checks pass. That is a more useful success measure than a target number of files or lines deleted.
