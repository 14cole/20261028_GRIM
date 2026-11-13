# Reproducing the solver-methods study

Production source is the unchanged `09fec5b2663649e859f292211c9d490e6b9f615b` tree on `codex/solver-numerical-followups-2026-11-12`. The research branch adds only files under this audit directory. `PRODUCTION_UNCHANGED.json` in the evidence checks all 526 non-audit blobs, including shipped native libraries. The backend Python digest is `817d4cc7fee52b3b5b34d10380e4277d6bcb91bb4f0a2effc458fbf7947a3216`.

The `scripts/` directory provides directly reviewable copies of the experiment code; the verified archive also includes those scripts beside the raw results.

The scripts use Python 3.12, NumPy, SciPy, psutil and threadpoolctl. The current host had a four-CPU cgroup quota and a 16 GiB memory limit. See `FMM_BUILD_IDENTITY.json` for exact versions. Its existing assembly native libraries were enabled. This is not a 32 GiB desktop timing prediction.

## Evidence and paths

Run `python unpack_evidence.py /absolute/path/to/new-evidence-directory` to verify every archive part, reassemble it and verify every extracted file against `EVIDENCE_MANIFEST.json`. The archive preserves complete complex fields, densities where measured, JSON metrics, scripts, initial failed prototype runs, build logs and Claude's pinned reference evidence. `peak_rss_gib` is the process high-water mark; `peak_gib` in the inherited profiler is its end-of-run RSS and must not be substituted for peak RAM.

Run extracted scripts in a fresh output directory, copying the `*.py` helpers there. Existing nonempty result JSONs are deliberately skipped by the runners; **do not run a reproduction directly over the archived evidence and mistake skipped work for new execution**. Use an absolute repository root:

```bash
export GRIM_ROOT=/absolute/path/to/20261028_GRIM
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
python run_methods.py
python run_holdouts.py
python analyze_methods.py
```

`run_methods.py` performs 32 complete one-shot two-polarization solves, including Dense targets, geometrical scale tests, disk residuals and inverse policies. `run_holdouts.py` adds adjoint/random-RHS, lossless-star and thin-coating checks. These are discrete-system checks, not mesh certification. Ordinary solver runs allow the backend's existing automatic thread allocation; FMM experiments explicitly use one thread. Do not compare those clocks as if they used the same thread budget.

`method_hooks.py` and `research_hooks.py` are audit-only monkeypatches. They are not loaded by the application. Their spec is recorded with each result; a production-source hash alone does not identify an experimental policy.

For Claude's review verification, keep the extracted `claude_reference` directory beside `verify_claude_review.py` and run:

```bash
python verify_claude_review.py
```

That recomputes 36 field comparisons from 72 archived solves. `CLAUDE_FILE_IDENTITIES.json` records the 80 verified Git blobs from Claude commit `c4204e7410af8f204f9b6ee56467feaa95868825`. It is evidence recomputation, not a claim that this script reruns Claude's 72 solves.

## Building the external FMM experiment

The experiment uses FMM2D commit `7e7509ecd6ebe31b9292cb00825410b478f44808`:

```bash
git clone https://github.com/flatironinstitute/fmm2d.git
cd fmm2d
git checkout 7e7509ecd6ebe31b9292cb00825410b478f44808
make -j4 lib FC=gfortran \
  FFLAGS='-fPIC -O3 -std=legacy -fallow-argument-mismatch -w -fopenmp' \
  LIBS='-lm -fopenmp' DYLIBS='-lm -fopenmp'
export FMM2D_LIBRARY="$PWD/lib/libfmm2d.so"
```

We built with GNU Fortran 14.2.0-19 and default 32-bit Fortran INTEGER. The ctypes bridge uses `c_int` and is **not compatible with an unexamined default-integer-8 build**. No Windows DLL was built. The local binary hash and compiler flags are recorded in `FMM_BUILD_IDENTITY.json`.

On this host no Fortran compiler was initially available. We downloaded and extracted `gfortran-14-x86-64-linux-gnu`, `libgfortran-14-dev` and `libgfortran5` into `/workspace/fmm-libraries/toolchain`, without a system installation. The successful command substituted:

```
FC='/workspace/fmm-libraries/toolchain/usr/bin/x86_64-linux-gnu-gfortran-14 -B/workspace/fmm-libraries/toolchain/usr/lib/gcc/x86_64-linux-gnu/14 -B/usr/lib/gcc/x86_64-linux-gnu/14'
LIBS='-lm -fopenmp -L/workspace/fmm-libraries/toolchain/usr/lib/gcc/x86_64-linux-gnu/14'
DYLIBS='-lm -fopenmp -L/workspace/fmm-libraries/toolchain/usr/lib/gcc/x86_64-linux-gnu/14'
```

Its runtime used `LD_LIBRARY_PATH=/workspace/fmm-libraries/toolchain/usr/lib/x86_64-linux-gnu`. On a machine with the compiler installed normally, use the appropriate system runtime instead. The runners' archived LD_LIBRARY_PATH is a harmless nonexistent path on other hosts with a system libgfortran, but should be adjusted if a different custom runtime is required.

From the directory containing the extracted research scripts:

```bash
python fmm_native.py
python test_fmm_operators.py
python run_fmm_benchmarks.py
python run_fmm_systems.py
python run_fmm_galerkin_benchmarks.py
python analyze_fmm.py
```

Run suites sequentially to avoid timing interference. `queue_holdouts.py` and `run_queued_fmm.py` only orchestrated the original session; their original PID/path waits are not portable reproduction commands.

`fmm_native.py` checks point charges, gradients and dipoles for real and lossy wavenumbers. The Galerkin tests compare S, K, K' and W on three meshes. The point benchmarks retain full outputs but validate only 32 sampled targets. Complete-system tests use both a dense reference and near-band ILU, and retain those dense allocations: their process peak RAM is **not an FMM-only capacity result**. The large Galerkin product runner evaluates both S and W before any exact-row reference assembly, keeping its validation allocations out of the reported product peaks. It stores all product outputs and the exact sampled rows. The analytic circle checks additionally test physical orientation and material-side conventions. Star tests are same-mesh discrete comparisons, not analytic validation or mesh convergence certificates.

## External dependency provenance

The pinned repository's root `LICENSE` is Apache-2.0, while `src/helmholtz/hfmm2d.f` retains GPL-2.0-or-later notices. The documentation's BSD statement refers to its older FMMLIB2D ancestor. These are conflicting notices that require provenance clarification before distribution integration. No FMM2D source or binary is redistributed in this evidence package; obtain it directly from the pinned upstream source for reproduction. This research does not resolve licensing or Windows packaging. The application's existing DLL/.so files are unchanged.
