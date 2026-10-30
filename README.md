# GRIM, GHOST, and FREDDY

This is the application distribution. Keep GRIM_Backend and tools together.

## Windows setup

1. Install 64-bit x64 Python 3.11 or later.
2. Extract or clone the entire repository into a writable folder.
3. Run Setup_GRIM.bat. It creates .venv and installs the dependencies from
   requirements.txt; internet access is required for the initial installation.
4. Run Launch_GRIM.bat to open GRIM with its GHOST and FREDDY tabs.

Python and third-party dependencies are installed separately; they are not
embedded in this repository. The supplied native solver DLLs target Windows
x64 and require no C compiler on the user's computer.
[Native library checksums](tools/GHOST/NATIVE_LIBRARIES.json) identify their
source and binary versions.

The standalone launchers are tools/GHOST/Launch_GHOST_GUI.bat and
tools/FREDDY/Launch_FREDDY_GUI.bat; both prefer the shared .venv.

For an already configured Python environment, run:
python GRIM_Backend/run_gui.py

PowerPoint integration requires Microsoft PowerPoint installed on Windows.
GPU acceleration is optional and needs a compatible GPU environment; the
standard installation uses the CPU solvers and bundled native kernels.

## Guides

- [GRIM application guide](GRIM_Backend/docs/README.md)
- [Assembly workflow](GRIM_Backend/docs/ASSEMBLY_WORKFLOW.md)
- [GHOST solver guide](tools/GHOST/README.md)
- [FREDDY materials guide](tools/FREDDY/README.md)
- [GHOST native libraries and packaging](tools/GHOST/DISTRIBUTION.md)

Run python tools/GHOST/scripts/check_speed_paths.py to inspect available
native and BLAS acceleration. Sample geometries, material tables, and feature
placement templates remain alongside their tools.
