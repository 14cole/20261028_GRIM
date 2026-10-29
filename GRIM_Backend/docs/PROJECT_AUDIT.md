# Project audit (2026-10-16)

Scope: the whole GRIM application: backend architecture, the dataset model, storage and
memory, execution and concurrency, release and repository hygiene, and the test suite.
Performance hotspots from the 2026-10-15 survey stay in `OPTIMIZATION_CANDIDATES.md` and
are not repeated; items here cite them where the causes overlap. The three tabled designs
(shared immutable sample storage, an indexed native format, per-format import prompts) are
not re-proposed.

Method: seven read-only code audits by area, an AST scan of the import graph and sizes, a
timed run of the full test suite, and reproduction scripts for crash claims. Every finding
marked "verified" was re-checked against the code or by running it; "reproduced" means a
script showed the failure on this machine. Item IDs (A1, B2, ...) are used for
cross-references.

## Summary

### Defects to fix first (verified or reproduced)
| ID | Defect | Effort |
|---|---|---|
| E1, C2 | Exiting while work runs crashes the process: a segmentation fault when a pool job still reads a disk-backed buffer (3 of 3 runs), and a Qt abort when the interference thread is running, which the main window never guards | S |
| A1 | The hash-pinned release bundle ships 74 files from GHOST's audit folders, including 15 research DLLs, because the exclusion list names a folder that does not exist | S |
| C1 | GUI CDF and waterfall plots are silently left out of the recorded Python script | S |
| E3 | Post-job work is lost: import failures vanish from the summary after a frequency-unit reload, a queued ISAR request is dropped, and an exception leaves the dataset buttons disabled | M |
| E4 | Cancel reports "nothing was published" after an export or save has already written files | M |
| D3 | A failed plot publication closes snapshots that the visible figure still reads; the next hover can crash | S |
| C8, D4, D2 | Three plot paths, the sweep envelope spool, CDF workspaces, report folders and assembly builds ignore the chosen working folder or Disk policy; 152 orphaned preview folders sit in `%TEMP%` | S-M |
| C8, E5 | A scoped storage call permanently changes the application RAM budget, and a one-time "Continue once" choice can leak into the next unrelated job | S |
| D8 | Independent copies of a disk-backed array keep its temporary folder alive | S |
| C11 | Every GHOST load adds duplicate `sys.path` entries and exposes GHOST's packages as top-level module names | S |
| B2, B8 | The same file loads into different internal representations depending on the load route, and the `rcs_domain` tag can contradict the stored data | M |

**Status, 2026-10-16:** every defect in this table was fixed the same day, each with a
regression test; see the shutdown and storage notes in `ARCHITECTURE.md`. Deliberate limits:
- B2: a full Disk-mode load now chooses the same representation as a RAM load. A region
  load still keeps the stored samples bit for bit, because existing tests pin that a region
  equals the same cells of a full load, and a region can be convertible when the file is not.
- B2: the native loader's rejection of negative or infinite power is a documented, tested
  integrity rule and was kept. Construction now rejects nonfinite axis values, which saving
  would reject, so such a grid can no longer be built and then fail to save.
- C11: GHOST's backend folder stays on `sys.path`, because GHOST loads its root-level modules
  by bare name; the growth from repeated loads is fixed.
- D2: report previews follow the working folder and empty previews older than a day are
  swept; the delete-on-close cache redesign remains open.
- Still open from sections C-E: the ledger (D1), the job service (E2), modal nesting of
  completions (E3), busy gating while ISAR runs (E6) and Play pacing (E9).

### Structural priorities
| Area | Direction | Items |
|---|---|---|
| Execution | One job service with a shutdown drain, commit-aware cancel, one error envelope and structured progress | E2, E4, E7, E8 |
| Memory | One ledger that every subsystem claims from, and one working-folder rule | D1, D4, D6, D7 |
| Application | Explicit catalog, selection and job state instead of mixins; registries that drive plot modes and operations | C3, C4, C5, C9 |
| Dataset model | One validation entry point, a simpler sample store, typed metadata, an operation framework | B1-B5 |
| Layering | A format registry to remove the datasets-io cycle; the ISAR engine out of the plot modes | C7, C10 |
| Hygiene | Logging and crash capture, one atomic-write helper, packaging with console scripts | A3, A4, A8 |
| Tests | Parallel runs and a fast subset | F |

## A. Release, repository and code hygiene

### A1. The release bundle ships GHOST's audit artifacts, including 15 research DLLs (verified)
- Where: `release_validation.py:23-24` excludes a folder named `Codex_Audit`; the folder in
  the tree is `tools/GHOST/Claude_Audit`. `source_inventory` (60-84) accepts any `.dll`
  under a path segment named `native`, which matches `Claude_Audit/results/*/native/`.
- Verified: replaying `source_inventory` without hashing selects 674 files (16.5 MB);
  74 of them (3.4 MB) come from `Claude_Audit` and `tools/GHOST/scripts/audit_2026-10-06`,
  including 15 DLLs such as `Claude_Audit/results/agent_2d_assembly/native/far_fast.dll`.
  `export_bundle` copies exactly this inventory into the hash-pinned release.
- Fix: exclude by pattern (`*_Audit`, `audit_*`) and add a test that the inventory holds no
  audit path and no DLL outside `ghost_backend/**/native`. Effort S. Risk low.

### A2. Repository noise and missing ignore rules
- `tools/GHOST/Claude_Audit` is 29 MB in 465 files (two pickles of 9.9 MB, 31 DLLs,
  3.8 MB of profiler output, JSON with absolute user paths). 41 `__pycache__` folders
  (15.7 MB) are not ignored. Stray user files sit in the source tree: `airfoil.geo` at the
  root, `GRIM_Backend/foil.csv` and `GRIM_Backend/Drawing 2.csv` (verified present; the
  release filter happens to skip the CSVs).
- `GRIM_Backend/.gitignore` has five patterns; there is no root `.gitignore` and no
  `.gitattributes`.
- Fix: move audit material out of the tree, ignore `__pycache__/`, `*.pyc`,
  `.pytest_cache/`, delete the stray files. Effort S.

### A3. No logging, no crash capture, about 160 broad exception handlers
- `logging` is imported by 0 of 154 modules (verified by scan); there is no
  `sys.excepthook`, `threading.excepthook` or `faulthandler`.
- About 160 `except Exception` handlers; the hygiene audit classified 85 as converting the
  error to a message string (traceback lost) and 39 as swallowing it. Example:
  `integrations/ghost.py:235` and `integrations/freddy.py:285` keep only `str(exc)` when an
  embedded tool fails to load. `io/xpatch.py:260` `read_ss(verbose=True)` prints about 20
  lines by default for script callers.
- Cost: a failure in a worker thread or embedded tool leaves nothing to diagnose after
  the fact.
- Fix: a small logging setup called from `ui/app.py` `main()` and the headless entry
  points (rotating file under `%LOCALAPPDATA%\GRIM\logs`, both excepthooks,
  `faulthandler`), then convert string-only handlers to `logger.exception(...)` while
  keeping the user-facing text. Effort M. Risk low.

### A4. Atomic file publishing is hand-rolled 29 times
- 29 `os.replace`/`os.rename` publish sites in 18 modules, 14 different staging prefixes
  (`.grim-write-`, `.grim-flat-csv-`, `.pio-write-`, `.isar-stage-`, ...), and `fsync` in
  only 7 of the 18 modules. `io/batch.py` carries its own backup-and-rollback copy, also
  duplicated in GHOST and FREDDY. The cache-owner machinery exists twice
  (`datasets/result_storage.py:27-105` and `io/native_cache.py:26-63`).
- Cost: durability differs by writer and crash leftovers cannot be cleaned with one rule.
- Fix: one `staged_path(target, fsync=True)` context manager and one
  `publish_with_backup`, one staging prefix, one cache-owner base. Migrate small writers
  first and `io/batch.py` last. Effort M. Risk medium (Windows replace semantics while
  maps are open).

### A5. Available-memory probing is copied four times with different fallbacks (verified)
- `datasets/memory.py:16-59`, `execution/dataset_jobs.py:28-68`, `io/csv.py:197-230` and an
  inline probe in `datasets/transforms.py:337-352`. When RAM is unknown the budget falls
  back to 2 GiB in `datasets/constants.py`, `isar/memory.py`, `io/csv.py` and
  `ui/dataset_actions.py`, but to 512 MiB in `execution/dataset_jobs.py:73` and
  `datasets/result_storage.py:59`. `psutil` is a declared hard dependency, so the ctypes and
  sysconf fallbacks only run in unsupported environments.
- Fix: one `available_memory_bytes()`, one `default_budget_bytes(fraction)`, one byte
  formatter (three exist). Effort S. Risk low (keep the patched names as aliases for tests).

### A6. Constants with one name and several values (verified)
- `BLOCK_CELLS` is 65,536 in `datasets/result_storage.py` and `reduction_workspace.py`,
  32,768 in `io/binary_storage.py` and 262,144 in `io/native_cache.py`.
  `REDUCTION_BLOCK_CELLS` is 262,144 in `plotting/modes/common.py:27` but an alias of
  65,536 in `ui/dataset_actions.py:257-259`.
- Tolerances: `1e-6` appears 89 times (30 signature defaults `tol=1e-6`), `1e-12` 72 times,
  `1e-9` 56 times; the inclusive sweep-count idiom uses `1e-9` in eight places and `1e-12`
  in three. dB floors differ by module (`1e-12`, `1e-30`, NaN, -inf). The speed of light is
  defined twice and inlined five times. Figure dpi is 90, 100, 120, 160 or 200 depending on
  the path.
- Fix: named constants in `datasets/constants.py` (axis match, power and phase tolerances,
  dB floor, two block sizes) and one `sweep_count()` helper, values unchanged. Effort M.

### A7. Dead code, unused imports and oversized facades (verified samples)
- pyflakes reports 211 unused imports outside the tests; 86 of them are in
  `ui/dataset_actions.py` and `assembly/panel.py` (leftovers from earlier splits).
- 11 module-level functions have no references at all, e.g. `plotting/image_analysis.py:313`
  `_sample_grid` (verified); a cluster of eight in `plotting/modes/isar_mode.py`.
- `assembly/tree.py:1119` `_item_to_dict` is a retired serializer that 11 test calls still
  exercise, while the live save path is `_item_to_save_snapshot`.
- `datasets/api.py` re-exports 49 names; only `RcsGrid` is consumed. 56 underscore names in
  the facades have no consumer.
- GHOST keeps Python 3.6 shims (`execution/_dataclasses.py`, 1,184 lines;
  `execution/thread_control/_threadpoolctl_py36.py`, 821 lines) although its
  `pyproject.toml` requires Python 3.10.
- Fix: delete, trim the facades, point the tests at the live serializer. Effort S.

### A8. Dependencies, packaging and launch
- GRIM has no `pyproject.toml`; the only manifest is `offline packages/requirements.txt`,
  whose floors equal this machine's versions (numpy>=2.0, scipy>=1.16, matplotlib>=3.10,
  PySide6>=6.10, psutil>=7) and which lists `pywin32>=311` without a platform marker
  (verified). pytest is undeclared. `GRIM_Backend` has no `__init__.py`.
- The release runtime is Python 3.14.6 but only 3.11.0 exists on this machine, so the
  shipped interpreter is never tested here.
- Four identical `run_*.py` stubs and 15 `sys.path` edits replace console scripts;
  `integrations/ghost.py:156-158` rewrites `sys.path` at runtime.
- Fix: a root `pyproject.toml` with console scripts (`grim`, `grim-headless`,
  `grim-diagnostics`), a dev requirements file, lower bounds that are actually tested, and a
  test run on the release interpreter. Effort M.

### A9. Documentation drift (verified samples)
- `docs/README.md:1222-1227` documents a `grim-headless` command that does not exist.
- The README gives two test commands (`unittest discover` and pytest with `--basetemp`);
  `--basetemp` is no longer needed since the tests conftest handles the blocked temp root.
- 9 of 87 relative links are broken; six `GRIM_*` environment variables are undocumented
  and parsed three different ways (two crash at import on a malformed value).
- Fix: correct the lines, add an environment-variable table. Effort S.

### A10. Typing and size
- Return annotations cover 53% of functions overall but 9.8% in `datasets` and 20.9% in
  `io`, the numerical core; there is no type-checker configuration.
- 9 modules exceed 2,000 lines; 70 functions exceed 150 lines and 25 exceed 300. The
  longest are `assembly/panel.py` `_build_ui` (1,166 lines) and `GrimCutWindow.__init__`
  (882 lines).
- Fix: annotate `datasets` and `io` first and enable a checker on those packages only;
  split the long UI builders when they are next touched. Effort L, incremental.

### A11. Line endings
- The repository mixes CRLF and LF files with `core.autocrlf=false` and no `.gitattributes`.
  Three test files were already mixed before this work. My earlier patch scripts had
  converted 19 edited files from CRLF to LF; that is corrected (section G).
- Fix: a `.gitattributes` that fixes the convention and one whitespace-only normalization
  commit. Effort S.

## B. Dataset model and operation API

### B1. One grid has many internal representations, and every operation re-branches on them
- Where: `datasets/grid.py:109-115`, `datasets/storage.py:141-157, 256-268, 416-493`,
  `grid.py:372-438, 511-595`.
- Today: the sample store is the product of a storage kind (complex, power, power/phase,
  legacy power/phase), a domain (physical, raw field), nullable arrays, legacy-exposure
  flags with a SHA-256 fingerprint, and an optional raw amplitude pair in `extra` that can
  be authoritative over the stored field. The data-model audit counted 35 branch sites
  outside `grid.py` and `storage.py` (wrap, flip, offset, shift, interpolate, align, joins,
  stitch, overlap, native save, assembly).
- Verified: for a raw-field grid, `extra["rcs_amp_real"]` shares memory with the stored
  samples, so copying `extra` is sometimes a large copy and sometimes an alias.
- The legacy mutable path (`rcs_power`/`rcs_phase` setters, `_storage_peers`, fingerprint
  rehashing) is used by no application module and by 529 references in 68 test files.
- Fix: a `SampleStore` with three variants (complex field with domain, power only,
  power with phase) behind the existing properties; the raw pair becomes a property of the
  raw-field variant only; legacy arrays become read-only materialized copies. Migrate the
  branch sites to the store interface, then convert the test edits to `set_power_phase`.
  This is a simplification of the current model, not the tabled copy-on-write design.
- Effort L. Risk high (numerical equivalence on seam and raw paths).

### B2. The same file loads into different representations, and validation verdicts disagree (verified)
- A version-1 `.grim` archive loads as complex storage through `RcsGrid.load(path)` but as
  power/phase storage with `storage="disk"` or any region selection (verified), because the
  disk path builds grids through `_native_grid_instance` instead of the constructor.
  Downstream operations then take different numerical paths for the same data.
- The constructor repairs power (negative to 0, infinity to NaN; verified, audit reports
  only "warning"), while the native validator rejects negative power in files, and stitch
  and audit each have their own rule. Non-finite axes are accepted at construction and
  rejected only when saving (verified), so a script can build a grid it cannot save.
- Phase wrapping is implemented eight times, NaN-pair normalization about ten times,
  polarization-label cleaning five times with different rules.
- Fix: one Qt-free `datasets/validation.py` with `canonical_axes`, `clean_samples` and
  `choose_store`, each in repair, reject or report mode; the constructor, both loaders,
  the native validator and audit call it, keeping their current messages as the report
  mapping. Effort M. Risk medium (pinned error texts and audit codes).

### B3. Metadata lives in two untyped dicts with about 60 live keys
- 28 `*_json` keys hold JSON text that becomes a 0-d array after a native round trip, so
  about 25 readers repeat `np.asarray(raw).reshape(()).item()`, `json.loads` and a broad
  `except`. Six convention keys are read from either `units` or `extra`; a boolean flag is
  written as `True` but parsed as str, bytes or bool. Unit and quantity canonicalizers exist
  at least nine times with different alias sets (`io/csv.py` accepts `pm180`,
  `calibration.py` accepts `dbm2`).
- Fix: a typed `DatasetMetadata` view (axis units, quantity, phase wrap, conventions,
  provenance records) that serializes to the same keys, one alias table per unit type.
  On-disk key names and JSON layouts stay identical. Effort L. Risk medium.

### B4. Operations share no framework
- 42 `@dataset_operation` sites (verified count) choose among five ways to construct a
  result, three metadata policies (two functions are both named `_derived_response_extra`
  with different behaviour) and two history conventions. One operation writes two history
  lines (verified for `convert_axis_units`), and the GUI adds a third unless the operation
  recorded itself. Each operation hand-rolls its block loop, NaN cleaning, adoption and QA
  record; the GUI repeats the operation name in the decorator, the publish closure and the
  result details.
- Fix: an `OpSpec` (kind, dtype policy, metadata policy, detail text) and three runners
  (`run_exact`, `run_elementwise`, `run_reduction`) that own allocation, block schedule,
  cleaning, adoption and one history entry. Port `offset_db` and `incoherent_add` first.
  This also removes the adoption trap behind optimization item 3.2.
- Effort L (M for the framework, S per ported operation). Risk medium.

### B5. Precision policy is six local rules
- A float32 grid stays float32 through crop and incoherent add but becomes float64 after
  interpolation; `real_dtype` changes when a float64 raw pair is attached. Loaders choose
  complex64, float32 or float64 per format.
- Fix: state one policy on `OpSpec` (exact and elementwise keep source precision;
  interpolating and reducing compute in float64 but retain source precision unless asked;
  raw fields, calibration and hashes are float64; axes float64) and implement it once.
  Effort M. Risk medium (some tests pin float64 results).

### B6. Selection semantics differ by entry point (verified)
- `get_by_value` matches exactly (`tol=0.0`, `grid.py:814`), `axis_crop` matches within
  1e-6 in the axis's stored unit (a thousand-fold different physical tolerance for Hz and
  GHz files), `align_to("intersect")` is the only unit-aware matcher, and scripting requires
  unique matches. Some operations return a grid or `(grid, report)` depending on a flag,
  and no-op calls return `self`.
- Fix: one `AxisSelector` (values, inclusive ranges, strides, unit-aware tolerance) used by
  every selection entry point; reports as a separate function or attribute. Effort S-M.

### B7. Public attributes are mutable, mutated after construction, and alias memory
- `operations.py:259-263` replaces `result.extra` after construction; the native loader sets
  `units`, `history` and `source_path` afterwards; `load_storage` and
  `_operation_storage_options` are dynamic attributes present on some grids only.
- Fix: read-only metadata views plus `grid.with_metadata(**changes)`; one storage-info field
  set at construction. Effort S-M.

### B8. The `rcs_domain` tag is dead and can be wrong (verified)
- A power-only grid reports `rcs_domain == "power_phase"` (verified); save ignores the
  attribute and recomputes it from the storage kind. More than 70 constructor calls still
  pass a literal.
- Fix: make it a read-only property derived from the store; accept and ignore the keyword
  for one release. Effort S. Risk low.

### B9. Too many names for one thing
- `rcs=` accepts a complex field, a stacked real/imaginary array, or a real array silently
  treated as power. Seven names describe storage (`rcs_domain`, `rcs_storage_domain`,
  `storage_domain`, `storage_kind`, `sample_storage`, `load_storage`, `power_domain`); six
  ways read the field. Several operations exist as both a method and a function under
  different names (`axis_crop`/`crop_dataset`, `interpolate_axis`/`regrid_axis`).
- Fix: split `rcs=` into `field=` and `stacked_iq=`, keep one public verb per operation
  with deprecation shims. Effort S.

### B10. Assembly re-implements grid construction and raw normalization
- `assembly/tree.py:2972-2990, 3072-3080, 3619-3636` builds axes-only grids with full-size
  stubs, copies interpolation results through the constructor, and rescales a raw pair with
  its own copy of the normalization formula.
- Fix: `RcsGrid.from_field(...)` and `axes_only(...)` factories and one raw-normalization
  helper shared with `grid.py`, `native.py`, `axes.py` and `transforms.py`. Effort S-M.
  (The memory cost of the same lines is optimization items 5.4 and 5.5.)

## C. Application architecture

### C1. GUI CDF and waterfall plots are never written to the Python script (verified bug)
- Where: `scripting/recorder.py` `record_plot` keeps its own `supported` set of six modes;
  `plotting/registry.py` marks eight modes headless, including `cdf` and `waterfall`, and
  `scripting/plotting.plot_datasets` replays both.
- Effect: every CDF or waterfall plot made in the GUI is recorded as "plot was not
  recorded: the current headless recorder supports ... only", so the generated script
  silently lacks it. No test covers GUI recording for these two modes.
- Fix: derive the recorder's set from `HEADLESS_PLOT_MODES` and add a parity test across the
  registry, the recorder and the Python-tab hint text. Effort S. Risk low.
- Cause: at least eight parallel mode lists exist (`ui/app.py:123-199, 804-809, 987-1058`,
  `plotting/actions.py:399-418, 439-447, 3151-3152`, `scripting/recorder.py:422-436`,
  `reports/workflow.py:80`); see C4.

### C2. Closing GRIM does not guard a running interference job (verified bug)
- Where: `assembly/interference.py:157-168` runs a `QThread`; its guard `can_close()`
  (282-286) cancels it and refuses the close. Only `AssemblyWorkspace.closeEvent`
  (`assembly/workspace.py:2968-2970`) calls that guard, and the workspace is an embedded tab
  that never receives a close event. `GrimCutWindow.closeEvent` (`ui/app.py:2492-2700`)
  checks the response comparison but never refers to the interference inspector.
- Effect: closing the application while interference metrics compute destroys a running
  `QThread`, which Qt reports as a fatal error.
- Fix: one busy registry that `closeEvent` iterates (first step of C3). Effort S.

### C3. The main window is about 460 members held together by an unwritten attribute contract
- Where: `GrimCutWindow(DatasetOpsMixin, PlotOpsMixin, QMainWindow)` (`ui/app.py:215-216`)
  plus `PlotMarkersMixin`, `PlotSliderMixin` and `DatasetPlotStyleMixin`. Three aliasing
  layers sit on top: 85 plot-context fields exposed as window properties that follow the
  active tab (`plotting/session.py:52-95`), 17 sidebar widgets copied onto the window
  (`ui/app.py:457-458`), 23 `btn_*` attributes rebound on every tab change (2197-2220).
- Each mixin reads attributes the other creates, mostly through the 383 `getattr(self, ...)`
  fallbacks measured in the appendix. A fallback hides a broken contract: the
  `lbl_dataset_selection_summary` label is never created anywhere, so the 60-line branch
  that fills it (`ui/dataset_actions.py:1512-1574`) can never run (verified).
- State that should be explicit objects lives in widgets and flags: the dataset catalog is
  stored in table-item roles and rebuilt from rows (`app.py:2271-2305`); selection is split
  across the table and four lists; three schedulers coordinate through flags (dataset jobs,
  ISAR, plot jobs; see E); the plot session is an untyped dict; recording is driven from
  30 call sites and a 345-line state machine (`plotting/actions.py:3032-3377`).
- Target: a Qt-free `AppState` holding a `DatasetCatalog`, `SelectionState`, a `JobService`
  and a notifier (C9); the window composes views and controllers instead of inheriting
  mixins. Order: busy registry for close (fixes C2), then job coordination, catalog,
  selection, recorder as an event subscriber, and finally controllers in place of mixins,
  keeping delegating methods under the names tests call (`_add_dataset_row` appears 95
  times in tests).
- Effort L (the first step S). Risk medium.

### C4. Plot modes: the registry is not the source of truth, success is read from status-bar text, and plot state hides on matplotlib artists
- Mode lists compete (C1). Success detection is a substring test on the status message:
  `if "updated" in str(self.status.currentMessage()).lower()` at `plotting/actions.py:301,
  3046, 3067`, so rewording a message breaks recording.
- The recorded plot spec is a positional tuple read as `spec[0]`...`spec[4]` in four places,
  including `reports/workflow.py:79-144`, which also reaches into the window's private plot
  contexts and the workspace catalog.
- 62 `_grim_*` attributes on figures, axes and artists carry the real plot model: dataset
  keys (41 uses, holding a UUID, an `id()` fallback or a tuple), native sample files, image
  records, the CDF distribution, the Delta Map result, the sector table, Hold signatures and
  layout flags that every render must reset (`actions.py:1245-1276`).
- Target: grow `PlotMode` into the full specification (toolbar, button, headless, recordable,
  Hold/PBP support, report kind) and generate the UI lists from it; split each mode into
  capture, prepare and draw steps (prepare already exists for four modes in
  `plotting/requests.py`); keep a typed `PlotRecord` on the session that owns the series
  records and resources and produces the script spec. Order: C1 fix, an outcome object
  instead of the text test (keep the message text, which 75 test assertions read), a
  dataclass for the spec, series records at the single `_register_plot_line` choke point,
  registry-generated toolbar, lazy mode imports. Effort L. Risk medium.

### C5. Adding one dataset operation means editing seven files
- Time gate touches 7 source files at 16 points: the operation, `datasets/operations.py`
  (three special cases), the panel button, tooltip and signal in `ui/app.py`, imports, the
  enable list and a 66-line handler in `ui/dataset_actions.py`, the dialog, the scripting
  exports and the recorder's script header. Decimate touches 7 files at 13 points.
- 38 handlers take about 2,800 lines of the dataset mixin, in four execution styles; the
  "created N dataset(s)" status is composed 24 times. What runs can differ from what is
  recorded: Wedge to Conic runs one method and records another function, equal only by
  convention (`ui/dataset_actions.py:5276-5329`). The CLI offers four operations.
- Target: a Qt-free `OperationSpec` registry (label, arity, function, script name,
  parameter schema, execution kind, byte estimate, dialog factory, output-name rule) that
  drives the panel, one generic handler, the recorder, scripting exports and a CLI
  `--op key --param k=v`. It complements the operation framework of B4. Port offset, flip
  phase and duplicate first. Effort M. Risk low-medium.

### C6. Business logic trapped in UI classes
- No headless equivalent, and not recorded: PIO and PTM batch export with portable names,
  staging and rollback (`ui/dataset_actions.py:5542-5640, 5760-5828`; CSV batch export is a
  private function); building a report from a saved recipe (`reports/workspace.py:2050-2367`
  reads widgets; the recipe file is a dump of widget attribute names); building an assembly
  tree (`build_assembly_grid` takes a `QTreeWidgetItem`, and the worker fakes one with
  `_BuildNode`); replaying a column-mapped import (the result has no source path); the RAM
  preflight estimates.
- Duplicated between GUI and headless: `scripting/plotting.py` `plot_datasets` (678 lines)
  redraws azimuth, waterfall, CDF and ISAR figures separately from the plot modes, and the
  wording has already diverged (the CDF zero-power note differs); the ISAR parameter
  dictionary is built twice and converted to options twice.
- Moves, each independent: `io/export.py` for batch exports plus recorder support,
  `reports/recipe.py` with a semantic recipe format (reader for the old one),
  `assembly/tree_model.py` with an `AssemblyNode` and the `.asy` codec, `isar/request.py`
  shared by GUI and headless, then shared draw functions per mode. Effort M-L in total.

### C7. The ISAR engine lives inside a GUI plot-mode module
- `plotting/modes/isar_mode.py` lines 1-3145 are Qt-free formation numerics; the scripting
  API, `isar/recipes.py` (private helpers), two other modes and the renderer import it.
  Importing `scripting.api` therefore loads all 12 plot modes, and
  `plotting/modes/common.py` (fan-in 38) also hosts axis selection, coherent-metadata
  validation, sector parsing and the snapshot-folder global, which is why `isar` and
  `reports` import upward.
- Fix: move the engine to `isar/formation.py` with `isar_mode.py` as a re-export shim, split
  `common.py` into selection, budgets and native-sample modules, make
  `plotting/modes/__init__.py` lazy, and add a boundary test that `scripting.api` loads no
  mode module. Effort S. Risk low.

### C8. The execution context is implicit, and two of its side effects are wrong (verified)
- Six context variables (result storage, import budget, work control, text discovery, ISAR
  memory, operation recording) and module globals (application RAM budget, snapshot folder,
  ISAR caches, an environment variable read at import) define how work runs. Each worker
  type re-enters them by hand; the plot job runner passes none.
- Verified: three plot paths open their own Auto storage scope without a folder
  (`az_vs_range_mode.py:301`, `range_freq_mode.py:149`, `isar_mode.py:2803`), so their
  spills go to the system temp folder rather than the folder the user chose.
- Verified: `operation_result_storage(application_ram_budget_bytes=...)` calls
  `configure_auto_ram_budget` and never restores it (`datasets/result_storage.py:160-169`),
  so a scoped call permanently changes the application budget.
- Cancellation has five conventions: `checkpoint()` raising `WorkCancelled`, explicit
  cancel callables, `PlotCancelled` (also used by a dataset-level preview),
  `InterruptedError`, and ISAR returning the string "ISAR computation superseded." from 50
  places, which the headless path turns into a `ValueError`.
- Target: a frozen `ExecutionContext` (storage policy, budgets, cancel, progress, notice
  sink) whose `bind()` enters the existing variables, passed to the plot runner and created
  once per job; one `Cancelled` base exception; the scoped API restores the budget.
  Effort M. Risk medium (threading).

### C9. Outcomes travel as status text, payload dicts, error strings and metadata flags
- 324 `status.showMessage` calls (175 in the dataset mixin), 115 workspace-local status
  setters, 43 message boxes; worker results are dicts with `ok`, `error`, `cancelled` keys;
  ISAR returns errors as strings; advisories ride inside dataset metadata. The frequency
  unit inference is acted on only by the GUI, so headless `load_dataset` accepts a guessed
  unit silently. Tests read the English text in 112 lines.
- Target: `Notice` (severity, stable code, message, subject) and `Outcome` (status, value,
  notices, skipped) types; a GUI notifier that produces today's exact strings; scripts turn
  advisories into warnings with the notice code. Effort M. Risk low.

### C10. Datasets depend on io, and format knowledge sits in five dispatch points
- `RcsGrid` inherits seven file-format mixins from `io` (`datasets/grid.py:30-54`), which
  creates the 17-module import cycle. Dispatch lives in two if-chains in `io/loaders.py`, its
  extension table, `io/binary_storage.py`, and a separate extension table with estimates in
  `execution/dataset_jobs.py:77-153`; writers are grid methods and batch fan-out is in the
  GUI.
- Target: a `FormatSpec` registry (extensions, sniff, load with `grid_class`, estimate,
  save, supported storage modes) in `datasets/formats.py` that imports io lazily by name; the
  flat CSV reader already takes `grid_class` as an argument, which is the precedent. Convert
  formats one at a time, native last, then add an AST layering test. Effort M. Risk medium.

### C11. GHOST and FREDDY boundaries are duck-typed and change process-wide import paths
- `integrations/ghost.py:155-158` removes only the backend folder from `sys.path` and then
  inserts both the backend and its parent at the front on every call (verified by reading),
  so repeated loads accumulate duplicate entries and expose GHOST's top-level packages
  (`assembly`, `execution`, `io`, `ui`, ...) as bare module names for the whole process. The
  interference recompute calls it on every interaction.
- `execution/diagnostics.py:139-361` hard-codes 68 GHOST module aliases, 123 required GHOST
  file paths and 28 FREDDY paths. Optional methods are found with `getattr` and fail open: if
  FREDDY drops `job_is_running`, GRIM treats it as idle and closes mid-job. GRIM's own
  table import subclasses FREDDY's converter dialog, and GHOST's own `.grim` reader accepts
  only format versions 1 and 2.
- Target: runtime-checkable protocols plus a contract version per tool, fail closed when a
  busy method is missing, load GHOST in a private namespace the way FREDDY already is, and
  a contract test that loads the bundled tools and round-trips a native file through
  GHOST's codec. Effort S-M. Risk low-medium.

## D. Storage and memory

### D1. No shared memory ledger: independent limits claim the same headroom at the same time
- At least eight limits each take a fraction of the free RAM they see when they start: the
  import limit (`datasets/memory.py:61-71`), coherent arithmetic (74-98), load batches and
  joins (`execution/dataset_jobs.py:176-182, 278-292`), derived outputs
  (`ui/dataset_actions.py:300-304`), ISAR (`isar/memory.py:16-40`), plot preparation
  (`plotting/requests.py:261-268`), the assembly build (`assembly/tree.py:2766-2771`), and the
  Auto allowance of one quarter of available plus managed bytes
  (`datasets/result_storage.py:51-59`). None subtracts another's outstanding plan.
- Dataset jobs refuse to start while ISAR runs, but ISAR starts without checking dataset jobs,
  and plot jobs, assembly builds, comparisons and report exports have no guard. A load batch
  plus an ISAR formation can jointly plan for the whole of free RAM.
- The Auto allowance counts only buffers made by `allocate_result`. The storage audit
  measured that a 144,720-cell grid loaded into RAM from CSV reserves 1.16 MB of allowance,
  while the same grid from `.grim` reserves nothing (`np.load` bypasses the allocator).
- Fix: one ledger service with atomic `claim(subsystem, nbytes, transient|retained)`,
  `retain(array, holder)` and a `snapshot()` for the UI, introduced first as a facade that only
  records claims with today's formulas. Effort L. Risk medium.

### D2. Private caches are reclaimed only by finalizers or a manual button (verified leftovers)
- Each mapped array gets its own `grim-result-*` or `grim-native-*` folder with a marker file;
  removal relies on `weakref.finalize`, two `atexit` retry hooks and the Clean button in
  Storage usage. Because `atexit` runs in reverse registration order, the native-cache retry
  runs before the finalizers, so a native cache that fails to delete during exit is never
  retried. After a crash, full-size sample files remain until the user presses Clean, and
  only in the currently configured folder.
- Verified: `%TEMP%` holds 152 empty `grim-ppt-preview-*` folders dated 11 to 16 October
  (2 from today's runs). The Reports workspace creates one per window
  (`reports/workspace.py:573-580`) and nothing sweeps old ones.
- Fix: back private mappings with delete-on-close temporary files, the pattern
  `NativeSamples` already uses, so Windows removes them when the last view dies or the
  process ends; run marker cleanup at startup over every folder ever used. Effort M.

### D3. Closing a plot snapshot unmaps memory that live artists still read
- `NativeSamples.close()` closes the mapping (`plotting/modes/common.py:128-139`), but artists
  keep views into it (`plotting/actions.py:1686-1695`). If publication raises after a
  snapshot is attached, `PlotResult.close` (`plotting/requests.py:66-75`) closes it while the
  partly drawn figure stays on screen; the storage audit verified that reading a view after
  close kills Python with a segmentation fault.
- Fix: transfer ownership when a snapshot is attached and release the partial figure before
  disposal; later, make snapshots owned by their views. Effort S. Risk low.

### D4. The working folder and the Disk policy are bypassed by several paths (verified samples)
- Plot paths open Auto scopes without a folder (C8); CDF population workspaces follow only
  the active policy; the sweep envelope spools with `tempfile.TemporaryFile()` without a
  folder and without a free-space check (`plotting/modes/common.py:687`, verified), up to
  about 1.6 GB for 100,000 sweeps of 2,001 frequencies; report preview and export folders go
  to `%TEMP%`.
- Assembly builds run with no storage policy and no `work_control`
  (`assembly/tree.py:3674-3685`, verified), so results and their float64 raw-pair extras stay
  in RAM even when the user chose Disk, and Cancel only works between tree nodes. A `.grim`
  dropped on the assembly tree loads in RAM on the GUI thread, ignoring Load options, and a
  budget refusal becomes an empty leaf (`tree.py:2030-2036`).
- Fix: one `working_folder()` rule (active policy, then configured folder, then `%TEMP%`) used
  by `allocate_result`, workspaces, envelopes and reports; wrap assembly builds in the
  captured options as dataset jobs already are. Effort S-M. Risk low.

### D5. Auto admission depends on order and batch
- An array is admitted to RAM only if it fits the remaining per-operation budget and
  allowance, and reservations last as long as the array. The storage audit measured
  `offset_db` of a 15.3 MiB grid spilling to disk at Auto budgets of 8, 12 and 20 MiB,
  because the precursor copy of optimization item 3.2 holds the budget when the retained
  result is allocated. A map job runs every selected row inside one context, so later rows
  spill regardless of their own size.
- Fix: `allocate_result(role="result"|"transient")` with a separate scratch allowance, and a
  per-row budget under a job cap. Effort S-M.

### D6. Deleted datasets stay alive through holders the Storage usage dialog cannot see
- The inline analysis panel keeps its datasets after deactivation; CDF state keeps dataset
  objects and a slice that pins the whole population workspace; assembly leaves share or
  deep-copy grids; the ISAR preprocessing cache keeps up to 512 MiB of managed arrays
  process-wide with no clear action; cut caches keep 64 MiB per panel. The dialog counts
  only table rows and the last undo batch.
- Fix: a retainer registry (holder, bytes, release action) shown in the dialog; CDF curves
  keep dataset ids instead of datasets; the ISAR cache evicts entries of deleted datasets and
  gets a Clear action. Effort M.

### D7. Observability and control lag behind what exists
- Storage usage shows five totals and omits snapshots, spools, caches, captures, assembly
  grids, folders in use and their free space. The result-storage settings default to Auto,
  256 MiB per operation and the system temp folder; load options default to RAM and 50% of
  available RAM; neither folder is validated until something spills. Four knobs exist only as
  environment variables. Spill feedback is a row tooltip; the load review shows RAM only
  although the disk need is computed; native extraction has no free-space preflight; the GUI
  offers no Auto load mode although headless loading has one; recorded scripts embed the
  temp folder path literally.
- Fix: a storage panel driven by the ledger and registry, a storage column in the Datasets
  table, one validated working-folder setting, and Auto plus disk need in Load options.
  Effort M.

### D8. Cache owners propagate into independent copies (verified)
- `__array_finalize__` copies the cache owner from any source array
  (`datasets/result_storage.py:108-110`, `io/native_cache.py:67-70`). Verified for a
  disk-backed managed array: `a*2`, `np.abs(a)`, `a.copy()` and `copy.deepcopy(a)` share no
  memory with `a` yet all carry its owner, so they keep its temporary folder on disk;
  `np.array(a)` does not. The assembly clone's `copy.deepcopy(grid)` pins the original's cache.
- Fix: inherit the owner only when memory is shared. Effort S. Risk low-medium.

## E. Execution and concurrency

### E1. Exiting while work runs crashes the process (reproduced)
- No drain phase exists: `ui/app.py` `main()` returns straight after `app.exec()`, nothing waits
  for `QThreadPool.globalInstance()`, and closing plot sessions only sets their cancel flags
  (`plotting/actions.py:1334-1349`).
- Reproduced: a pool job still reading a disk-backed buffer from GRIM's own `allocate_result`
  when the window closes ends in a segmentation fault in 3 of 3 runs; Python's exit handlers
  unmap the buffer under the running job. In GRIM this exposes plot preparations, inline
  analysis cuts and A/B captures that are mid-block on a Disk-mode dataset or managed result.
- Reproduced: a `QThread` parented to an embedded widget and still running at exit makes the
  process abort with Qt's fatal error code 0xC0000409 after the event loop has returned
  normally. The interference inspector has exactly this structure and is never guarded at
  close (C2). Its 500 ms planning timer is also started in the constructor and never stopped.
- Fix: connect `aboutToQuit` to a shutdown routine that cancels every job, calls
  `QThreadPool.globalInstance().waitForDone(timeout)` and waits on registered threads; add the
  interference guard; add a subprocess exit test asserting exit code 0 and no leftover cache
  folders. Effort S. Risk low.

### E2. Thirteen worker mechanisms with five cancellation styles and four queues
- Mechanisms: the dataset job slot (five worker classes), loader fan-out pools, ISAR, eight
  `PlotJobRunner` instances, response comparison, interference, library scan, assembly save,
  assembly build, feature operations, the placement surface helper, report export, and the
  table-import conversion. Cancellation is a context checkpoint, an event, `PlotCancelled`,
  `InterruptedError` or a returned string; queues are implemented four times.
- The ambient `checkpoint()` works only inside the dataset slot, loader pools and table import,
  so the same kernel (for example `align_to`) can be cancelled in one worker and not another.
- Fix: one job service (kinds, coalescing policy, priorities, exclusivity classes, one job
  context, one cancel token with a commit phase, structured progress, a result envelope
  delivered from `finally`, memory admission through D1). Register every existing start site
  first, which alone fixes E1 and E5. Effort L (M for the first two steps).

### E3. The post-job pipeline is re-entrant and loses work (verified by reading)
- `_on_background_thread_finished` runs mapping dialogs, unit dialogs, a button refresh, the
  memory review, the queue drain, the import summary and the ISAR resubmission in order, with
  no `try/finally` (`ui/dataset_actions.py:766-809`).
- Lost import summary: the frequency-unit reload calls `_handle_files_dropped`, which clears
  `_import_cycle_results` (line 1242), so a failure recorded earlier in the batch disappears
  from the final summary. That reload path was added in my previous implementation work.
- Lost ISAR request: the pending request is cleared before `_isar_submit` is called
  (803-809), and `_isar_submit` refuses without requeuing while a dataset job runs
  (`plotting/actions.py:2247-2256`), for example the import the drain just started.
- Completions run inside other completions' modal dialogs: a finished audit's report dialog
  hosts the next queued import and its mapping dialog, after which the audit's status text
  overwrites the import's.
- An exception in any phase leaves the dataset buttons disabled and the queue undrained.
- Fix: an explicit queue of post-job steps run from a zero-delay timer, a per-cycle summary
  object, requeue instead of refuse for ISAR, `try/finally`. Effort M. Risk medium.

### E4. Cancel is not aware of commit points (verified)
- Every background callable sets `supports_cancellation = True` and, if interruption was
  requested at any time, raises "cancelled" even after the function has returned
  (`execution/dataset_jobs.py:476-496`). A single-file PIO export therefore writes the file and
  then reports that nothing was published; a cancelled native save can replace every target
  while rows stay dirty. Audit and compatibility have no checkpoints, so Cancel waits for the
  full run and then discards the report.
- `WorkCancelled` derives from `RuntimeError` (`datasets/work_control.py:8`), so every broad
  `except Exception` must remember to re-raise it.
- Fix: a `commit()` phase after which cancel is ignored and the result says so; per-job cancel
  granularity in the UI; derive the cancel exception from `BaseException`. Effort M.

### E5. Per-job choices and global settings leak across jobs
- The one-time "Continue once" storage choice is kept on the window until the next background
  job starts (`ui/dataset_actions.py:532, 596-604`). Regrid can accept the review (3939) and
  then return on a metadata check (3950-3956) without starting a job, so the next unrelated
  operation runs with the leftover choice, including `allow_exceed`. (The execution audit also
  traced this through coherent operations; that path is unreachable because the coherent
  confirmation always returns False.)
- Every worker passes the application budget into its storage scope, which changes the
  process-wide value (C8).
- Fix: pass reviewed options into the job explicitly; set the application budget only on the
  GUI thread. Effort S.

### E6. Busy gating is inconsistent and refusals vanish (verified in part)
- `_background_job_active()` ignores ISAR (`ui/dataset_actions.py:558-563`, verified), so every
  dataset button stays enabled while ISAR or cine Play runs. Application-wide shortcuts open
  file and overwrite dialogs before the busy check, the job is then refused, and the refusal
  text is overwritten by progress messages within a tenth of a second.
- Fix: one `can_start(kind)` used by buttons, shortcuts (before any dialog) and close, and
  refusals shown as notices that persist (C9). Effort S.

### E7. Worker exceptions are flattened to text and sometimes dropped
- No path keeps a traceback; an exception with an empty message shows as "failed: "; the image
  comparison runner's `publication_failed` signal is not connected, so a publish error leaves
  the panel on "Preparing native image comparison..."; only the load worker emits its terminal
  signal from `finally`, so a `BaseException` elsewhere leaves the job slot busy forever and
  blocks close; assembly falls back to `print`.
- Fix: one error envelope (type, message, traceback, stage) built in the runner, one presenter
  with details, terminal signals from `finally`. Effort S-M.

### E8. Progress plumbing is inconsistent
- 14 dataset operations start jobs without `reports_progress`, so their kernels' progress is
  dropped (medianize reports progress that goes nowhere); multi-file loads mix file counts and
  byte counts on one bar; CSV, CST, SENTRi and OUT loads show an indeterminate bar.
- Fix: a structured progress event with a per-task throttle, always connected. Effort M.

### E9. Slider Play can never show a slow frame (verified by reading)
- Play advances every 350 ms (`ui/analysis_controls.py:402-403`) and every render cancels the
  running preparation (`plotting/actions.py:1234-1242`), so a frame that takes longer never
  publishes; waterfalls of 2.9M cells take 0.29-0.56 s and 100,000-azimuth sweeps about 2 s.
  ISAR and range Play already advance only after publication.
- Fix: advance on publication, or skip ticks while a preparation is pending. Effort S.

## F. Test suite

### F1. Run in parallel: about 6 minutes becomes about 1
- The suite takes 386 s on one core of a 16-core machine; `pytest-xdist` is not installed and
  there is no dev requirements file. The test-suite audit split the 167 files into
  time-balanced groups run as parallel processes: 4 processes took 83 s, 8 took 52-53 s and
  16 took 39-40 s, all fully green. No shared paths, ports, unseeded RNGs or order
  dependence were found; every file also passes alone.
- Fix: add `pytest-xdist` to a dev requirements file and run
  `python -m pytest GRIM_Backend/tests -n 8 --dist loadfile` (expect 55-60 s with xdist's
  collection overhead). Do F2 first, because memory is what breaks. Effort S.

### F2. Test windows are never destroyed (verified mechanism)
- 332 tests in 31 files build the full main window in `setUp` and tear down with
  `deleteLater()` plus `processEvents()`. Verified: that leaves the widget alive; only
  `QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)` destroys it, and only three
  files call it. The test-suite audit measured two GUI files peaking at 5.4 GB with 238,282
  live widgets, against 282 MB with a flush.
- A naive flush is dangerous: destroying a window whose background worker still runs aborts
  the process with no summary (the same hazard as E1).
- Fix: an autouse fixture in the tests conftest that cancels and waits for running background
  jobs (bounded) and then flushes deferred deletes; the audit ran the whole suite green with
  it. Effort S.

### F3. Invocation and environment are not pinned (verified samples)
- A bare `pytest GRIM_Backend/tests/...` fails at collection with "No module named
  GRIM_Backend" (verified); only `python -m pytest` from the project root works, helped by 12
  test files that edit `sys.path` at import.
- 13 GUI test files neither set nor inherit `QT_QPA_PLATFORM`, so run alone they open real
  windows. `GRIM_*` environment variables leak in: a small `GRIM_MAX_CSV_GRID_GB` causes 38
  failures and `GRIM_ISAR_CACHE_MB=0` four. 42 tests build the window with the real
  `QSettings("GRIM", "GRIM")` (verified at `tests/test_gui_dataset_workflows.py:367`), and four
  files can write the real assembly draft folder under `%LOCALAPPDATA%`.
- Fix: a root `pytest.ini` (test paths, `pythonpath = . tools/GHOST`, markers) and conftest
  isolation (offscreen default, scrub `GRIM_*`, temporary folders and settings per session).
  Effort S.

### F4. No marks and no fast subset
- No `slow` or `gui` marks exist. GUI files: 72 files, 1,189 tests, 240 s; non-GUI: 95 files,
  2,229 tests, 114 s. A `-m "not gui and not slow" -n 8` subset would take roughly 10-15 s
  (estimate).
- The slowest tests point at real costs: the 16.6 s offset test exposes a per-frequency Python
  loop in the native raw-pair check (`io/native.py:341-366`; optimization item 4.7); the
  12.6 s overlay test makes 140 full Agg draws; my own OUT storage test from the previous
  session takes about 9 s under `tracemalloc` and should be slimmed.
- Fix: apply `gui` automatically from module content and `slow` from a list in
  `pytest_collection_modifyitems`. Effort S.

### F5. Test modules import each other
- 52 test modules import from 20 others (70 imports); ten copy `setUp`/`tearDown` from another
  module's class; `QApplication` is created at 58 sites; 98 grid-building helpers and 31
  hand-written wait loops exist. This works only under pytest's default import mode.
- Fix: shared fixtures or a `tests/support` module (`qapp`, a window factory with the
  F2 teardown, `make_grid`, `wait_until`), converting borrowers first. Effort M.

### F6. Tests read matplotlib internals
- `ax.collections[0]` appears 39 times in 19 files and `_grim_*` artist attributes 157 times in
  38 files, which blocks optimization item 2.1 and finding C4.
- Fix: artist helpers that understand both meshes and images, used before the drawing change.
  Effort M.

### F7. A third of test functions touch private members
- 675 of 2,072 test functions reach private attributes; `_add_dataset_row` alone appears 80
  times, and `_RendererHarness` hand-copies 38 window attributes for 13 modules. This blocks
  the mixin extraction of C3.
- Fix: seams first (`add_dataset(window, grid, name)`, a small plot-owner factory), then the
  refactor. Effort M-L.

### F8. Legacy mutable arrays in 68 files
- 481 reads and 101 writes of `rcs_power`/`rcs_phase`. Reading the attribute switches the grid
  into the legacy storage kind, so these tests exercise the legacy path rather than canonical
  storage; this blocks B1.
- Fix: read `power`/`phase`, write through `set_power_phase`, and keep one dedicated legacy
  test module. Effort L, mechanical.

### F9. Flakiness hazards
- Two wall-clock assertions (`< 0.5 s`) in `test_coordinate_list_view.py`, which I wrote in the
  previous session; `tracemalloc` peak assertions in 9 files; 31 deadline loops, one of which
  spins `processEvents()` without sleeping for up to 10 s; `test_gui_shell.py` starts three
  patches in `setUp` and stops them only in `tearDown`, so a failing constructor leaves them
  installed; one file changes the application font without restoring it.
- Fix: a shared `wait_until` with a sleep and a scalable timeout, `addCleanup` for patches, a
  font fixture, and relative rather than absolute timing checks. Effort S-M.

### F10. Coverage is unmeasured
- No coverage tool is installed. About 20,150 lines (22% of the backend) live in five GUI host
  modules reachable only through window tests. GHOST and FREDDY suites run separately, and the
  release interpreter (3.14.6) is not tested here.
- Fix: add `coverage` to the dev requirements and run it once with the parallel suite.
  Effort S.

## G. Correction made during this audit

The audit found that my own earlier implementation work (the 2026-10-15 import and
performance fixes) had changed line endings: its patch scripts read files as text and wrote
them back with `newline=""`, which converted 19 edited files from CRLF to LF and left
`io/csv.py` half CRLF, half LF. The repository stores these files with CRLF and has
`core.autocrlf=false`, so copying the work back would have shown every line as changed.

The 19 files were restored to CRLF on 2026-10-16. Content is otherwise byte-identical.
Measured against the untouched October 7 copy, the diff of that earlier work fell from
42,665 changed lines to 1,797, its real size. All files compile, and the full suite passed
afterwards (3,357 passed, 61 skipped, 0 failed, 364 s). New files from that work stay LF,
like about half of the existing files.

## H. Suggested order

1. **Defect fixes (days).** E1 and C2 (shutdown drain, interference guard), A1 (release
   exclusion and its test), C1 (recorder parity), E3 (per-cycle summary, ISAR requeue,
   `try/finally`), D3 (snapshot ownership), the folder and budget leaks of C8, D4 and E5, D8
   (owner inheritance), C11 (idempotent GHOST path handling), E6 (ISAR in the busy check),
   E9 (Play advances on publication). Most are S and independent.
2. **Diagnosability (days).** A3 logging and crash capture, E7 error envelope, A9 docs fixes,
   A11 `.gitattributes`.
3. **Execution and memory foundations (1-2 weeks).** E2 job service registration, then C8
   execution context and D1 ledger as facades over today's formulas; C9 outcome and notice
   types behind today's exact strings; D2 delete-on-close caches.
4. **Application structure (weeks).** C3 catalog, selection and job state out of the mixins;
   C5 operation registry with B4 operation framework; C4 plot records and a registry-driven
   toolbar; C6 headless exports, report recipes and assembly tree model; C7 and C10 layering.
5. **Dataset model (weeks).** B2 validation entry point first, then B1 sample store, B3 typed
   metadata, B5 precision policy, B6 selection, B8 and B9 cleanups.
6. **Packaging and tests (in parallel).** A8 pyproject and console scripts, a test run on the
   release interpreter, and the test-suite changes in F.

Performance work from `OPTIMIZATION_CANDIDATES.md` can proceed alongside; its quick GUI
items, CSV vectorization and image drawing items do not depend on the restructuring here.

## Appendix: measurements

All numbers come from this machine on 2026-10-16 (system Python 3.11.0, numpy 2.4.2,
scipy 1.16.3, matplotlib 3.10.8, PySide6 6.10.2, psutil 7.2.2, 16 logical cores), from an
AST scan of `GRIM_Backend` excluding tests, examples and `python_env`.

### Package shape
| Measure | Value |
|---|---|
| Modules | 154 |
| Internal import edges, top level | 338 |
| Internal import edges, inside functions | 162 |
| Functions over 150 lines / over 300 lines | 70 / 25 (of 3,080) |
| `getattr(self, ...)` fallbacks | 383 (156 in `plotting/actions.py`, 90 in `ui/dataset_actions.py`) |
| `except Exception` handlers | 161 |
| Handlers that only `pass` or `continue` | 71 |
| Modules importing `logging` | 0 |
| TODO/FIXME/HACK markers | 0 |
| Modules using a thread, pool, timer or ContextVar | 25 |

### Layering exceptions (lower layer importing a higher one)
Layers: datasets < io < execution, isar < plotting < reports, assembly, scripting,
integrations < ui.

| Importer | Imports | How |
|---|---|---|
| `datasets.grid` | `io.cst`, `io.native`, `io.out`, `io.pioneer`, `io.ptm`, `io.sentri`, `io.xpatch` | top level (format mixins) |
| `datasets.api` | `io.cst`, `io.pioneer`, `io.ptm`, `io.samples` | top level |
| `execution.plot_jobs` | `plotting.requests` | top level |
| `integrations.freddy` | `ui.classic_theme` | top level |
| `reports.image_imprinter` | `ui.palette` | top level |
| `datasets.memory` | `io.native_cache` | inside a function |
| `datasets.transforms` | `plotting.requests` | inside a function |
| `isar.comparison` | `plotting.modes.common` | inside a function |
| `isar.recipes` | `plotting.modes.isar_mode` | inside a function |
| `plotting.image_display`, `plotting.modes.waterfall_mode` | `ui.image_analysis` | inside a function |

Import cycles once function-level imports are counted: one of 17 modules spanning
`datasets` and `io`; 7 modules in `plotting` plus `isar.comparison`; 4 in `datasets` storage
plus `io.native_cache`; 4 and 2 in `assembly`; 2 in `reports`; 2 in the ISAR plot mode.
No cycle exists among top-level imports alone, which is why the function-level imports
are there.

### Largest units
| Module | Lines | | Function | Lines |
|---|---|---|---|---|
| `ui/dataset_actions.py` | 6,138 | | `assembly/panel.py` `_build_ui` | 1,166 |
| `assembly/panel.py` | 5,276 | | `ui/app.py` `GrimCutWindow.__init__` | 882 |
| `assembly/tree.py` | 3,820 | | `ui/app.py` `_build_plot_left_context` | 712 |
| `plotting/actions.py` | 3,499 | | `datasets/combine.py` `stitch_many` | 695 |
| `assembly/workspace.py` | 3,199 | | `datasets/audit.py` `audit_dataset` | 685 |
| `plotting/modes/isar_mode.py` | 3,157 | | `scripting/plotting.py` `plot_datasets` | 678 |

| Class | Methods | Lines |
|---|---|---|
| `PlotOpsMixin` (`plotting/actions.py`) | 158 | 3,279 |
| `DatasetOpsMixin` (`ui/dataset_actions.py`) | 128 | 5,697 |
| `FeatureAssemblyPanel` (`assembly/panel.py`) | 93 | 4,113 |
| `PptWorkspace` (`reports/workspace.py`) | 72 | 2,173 |

### Test suite timing
3,357 passed and 61 skipped in 386 s on one core. The 80 slowest tests take 145 s (38%).

| File | Slow tests | Seconds |
|---|---|---|
| `test_spatial_overlays.py` | 4 | 18.4 |
| `test_offset_median_correctness.py` | 1 | 16.6 |
| `test_waterfall_cut_alignment.py` | 13 | 14.8 |
| `test_offline_setup.py` | 3 | 13.0 |
| `test_out_managed_storage.py` | 1 | 9.1 |
| `test_analysis_layout_regressions.py` | 3 | 7.1 |
| `test_line_expansion_compact.py` | 1 | 7.0 |
| `test_managed_ptm_text_io.py` | 1 | 4.7 |

