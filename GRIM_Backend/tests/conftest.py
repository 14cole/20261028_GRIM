"""Shared pytest configuration for the GRIM suite.

pytest keeps the ``tmp_path`` directories under ``<temp>/pytest-of-<user>``.
That folder can be left behind by another account (an elevated shell or a
different profile), after which every fixture-based test fails during setup
with "Access is denied" before any test code runs. When no ``--basetemp`` was
given and the default root is unusable, ``pytest_configure`` points pytest at
``<temp>/grim-pytest`` instead, where it keeps its usual numbered run folders
and the cleanup of old runs. Passing ``--basetemp`` or setting
``PYTEST_DEBUG_TEMPROOT`` yourself disables the fallback.
"""
from __future__ import annotations

import getpass
import os
import tempfile
from pathlib import Path

import pytest

FALLBACK_TEMPROOT_NAME = "grim-pytest"
TEMPROOT_ENV = "PYTEST_DEBUG_TEMPROOT"
TEMP_ROOT_NOTE = pytest.StashKey[tuple]()


def suite_user() -> str:
    """The user name pytest itself uses for ``pytest-of-<user>``."""
    try:
        return getpass.getuser() or "unknown"
    except (ImportError, OSError, KeyError):
        return "unknown"


def usable_pytest_root(root: Path) -> bool:
    """True when pytest could scan ``root`` and create its run folders there."""
    try:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        list(root.iterdir())  # pytest lists the root to number the next run
        probe = tempfile.mkdtemp(prefix="probe-", dir=root)
        os.rmdir(probe)
    except OSError:
        return False
    return True


def choose_temp_root(default_temproot: Path, fallback_temproot: Path) -> Path | None:
    """Return the temp root to use instead of ``default_temproot``, or None to keep it.

    The fallback is only used when pytest's own root is unusable and the
    fallback works; otherwise pytest reports its original error unchanged.
    """
    user = suite_user()
    if usable_pytest_root(default_temproot / f"pytest-of-{user}"):
        return None
    if usable_pytest_root(fallback_temproot / f"pytest-of-{user}"):
        return fallback_temproot
    return None


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    if config.option.basetemp is not None or os.environ.get(TEMPROOT_ENV):
        return
    default = Path(tempfile.gettempdir()).resolve()
    chosen = choose_temp_root(default, default / FALLBACK_TEMPROOT_NAME)
    if chosen is not None:
        os.environ[TEMPROOT_ENV] = str(chosen)
        config.stash[TEMP_ROOT_NOTE] = (default / f"pytest-of-{suite_user()}", chosen)


def pytest_report_header(config):
    note = config.stash.get(TEMP_ROOT_NOTE, None)
    if note:
        return f"tmp_path root: {note[1]} (pytest's default {note[0]} is not accessible)"
