"""The release ships only application files, and GHOST loading keeps sys.path stable."""
import sys
from pathlib import Path

import pytest

import GRIM_Backend.release_validation as release

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_audit_folders_are_recognized():
    assert release._is_audit_folder("Local_Audit")
    assert release._is_audit_folder("Development_Audit")
    assert release._is_audit_folder("audit_2026-10-06")
    assert not release._is_audit_folder("assembly")
    assert not release._is_audit_folder("audit.py")


def test_release_inventory_holds_no_audit_material(monkeypatch):
    if not (PROJECT_ROOT / "tools" / "GHOST").is_dir():
        pytest.skip("bundled tools are not present")
    monkeypatch.setattr(release, "sha256", lambda path: "not-hashed")
    paths = [entry["path"] for entry in release.source_inventory(PROJECT_ROOT)]
    assert paths
    assert not [p for p in paths if any(release._is_audit_folder(part) for part in p.split("/")[:-1])]
    stray_libraries = [p for p in paths if p.lower().endswith(".dll")
                       and not (p.startswith("tools/GHOST/ghost_backend/") and "/native/" in p)]
    assert stray_libraries == []


def test_repeated_ghost_loads_do_not_grow_sys_path():
    from GRIM_Backend.integrations.ghost import discover_ghost_backend, load_ghost_module
    backend = discover_ghost_backend(None)
    if backend is None:
        pytest.skip("the bundled GHOST backend is not present")
    saved = list(sys.path)
    try:
        for _ in range(3):
            load_ghost_module("ghost_backend")
        assert sys.path.count(str(backend)) == 1
        assert sys.path.count(str(backend.parent)) == 1
        assert sys.path[:2] == [str(backend.parent), str(backend)]
    finally:
        sys.path[:] = saved
