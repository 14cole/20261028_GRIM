# GHOST distribution and native libraries

The repository includes runtime code, user resources, launchers, four Windows x64 DLLs, and four Linux x86-64 shared libraries.
The Windows libraries are:

- ghost_backend/twod/assembly/native/ghost_table.dll
- ghost_backend/twod/assembly/native/ghost_far.dll
- ghost_backend/twod/assembly/native/ghost_near.dll
- ghost_backend/bor/native/bor_stream_kernel.windows-amd64.dll

Keep these files beside their Python wrappers. Windows x64 users need no
compiler. The shared root Setup_GRIM.bat installs the Python dependencies;
use Launch_GRIM.bat or the standalone Launch_GHOST_GUI.bat afterward.
The native libraries preserve the existing double-precision arithmetic and
use a portable x64 instruction baseline. Checksums and source identities are
recorded in NATIVE_LIBRARIES.json (Windows) and NATIVE_LIBRARIES_LINUX.json
(Linux).

Run python scripts/check_speed_paths.py from this folder to report available
native kernels and optimized BLAS. A missing or incompatible native library
uses the NumPy fallback and is reported as a slow path.

## Linux x86-64

The distribution also includes these compiled libraries:

- ghost_backend/twod/assembly/native/libghost_table.so
- ghost_backend/twod/assembly/native/libghost_far.so
- ghost_backend/twod/assembly/native/libghost_near.so
- ghost_backend/bor/native/bor_stream_kernel.linux-x86_64.so

They require glibc 2.35 or newer and libgomp.so.1 (the GNU OpenMP runtime,
usually supplied by the libgomp1 package). They were built with GCC 14.2.0
on Linux x86-64 and load-checked with every required export. They use the
x86-64/SSE2 instruction baseline and do not require AVX. These are Linux
binaries, not macOS, ARM, or universal manylinux binaries.

Python and the Python dependencies must still be installed. The loaders select
the matching platform library automatically; keep both platforms' files beside
their wrappers. Run the speed-path check above in the destination environment.

## Other platforms or rebuilding

For older Linux systems or another architecture, use the Python fallbacks
or compile matching libraries from the retained C sources:

    python ghost_backend/twod/assembly/native/build.py
    python ghost_backend/bor/native/build_kernel.py

The builders support Windows and Linux, require a C99 compiler, and load-check
all required exports before replacing a library. The BoR build enables OpenMP
when supported. Restart Python workers after rebuilding a loaded library.

## Optional Python packages

For package-based installation, the default build is portable and excludes
platform binaries. It differs from running this repository directly, which
uses the bundled DLLs or Linux shared libraries. A native wheel can be built on the target platform:

    python -m pip install "setuptools>=68" wheel
    python scripts/build_distribution.py --native --output ../native-distributions

This builds native libraries from staged C sources and produces a
platform-tagged wheel. A Windows x64 wheel includes all four DLLs. Linux wheels
include their Linux equivalents. Standard source packages remain portable.
The package builder retains the analytical cylinder/sphere references,
feature-comparison services, native sources, sample geometries and templates.
