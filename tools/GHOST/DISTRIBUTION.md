# GHOST distribution and native libraries

The repository includes runtime code, user resources, launchers, and four
validated Windows x64 DLLs:

- ghost_backend/twod/assembly/native/ghost_table.dll
- ghost_backend/twod/assembly/native/ghost_far.dll
- ghost_backend/twod/assembly/native/ghost_near.dll
- ghost_backend/bor/native/bor_stream_kernel.windows-amd64.dll

Keep these files beside their Python wrappers. Windows x64 users need no
compiler. The shared root Setup_GRIM.bat installs the Python dependencies;
use Launch_GRIM.bat or the standalone Launch_GHOST_GUI.bat afterward.
The native libraries preserve the existing double-precision arithmetic and
use a portable x64 instruction baseline. Checksums and source identities are
recorded in NATIVE_LIBRARIES.json.

Run python scripts/check_speed_paths.py from this folder to report available
native kernels and optimized BLAS. A missing or incompatible native library
uses the NumPy fallback and is reported as a slow path.

## Other platforms or rebuilding

The supplied DLLs are for Windows x64. Other systems can use the Python
fallbacks or compile matching libraries from the retained C sources:

    python ghost_backend/twod/assembly/native/build.py
    python ghost_backend/bor/native/build_kernel.py

The builders support Windows and Linux, require a C99 compiler, and load-check
all required exports before replacing a library. The BoR build enables OpenMP
when supported. Restart Python workers after rebuilding a loaded library.

## Optional Python packages

For package-based installation, the default build is portable and excludes
platform binaries. It differs from running this repository directly, which
uses the bundled DLLs. A native wheel can be built on the target platform:

    python -m pip install "setuptools>=68" wheel
    python scripts/build_distribution.py --native --output ../native-distributions

This builds native libraries from staged C sources and produces a
platform-tagged wheel. A Windows x64 wheel includes all four DLLs. Linux wheels
include their Linux equivalents. Standard source packages remain portable.
The package builder retains the analytical cylinder/sphere references,
feature-comparison services, native sources, sample geometries and templates.
