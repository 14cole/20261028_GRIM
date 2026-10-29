"""The suite falls back to a usable temp root when pytest's default one is blocked."""
import os
from types import SimpleNamespace

import conftest as suite_conftest  # pytest already imported it from this directory


def test_usable_root_accepts_a_new_folder_and_rejects_a_file(tmp_path):
    assert suite_conftest.usable_pytest_root(tmp_path / "new" / "root")
    assert (tmp_path / "new" / "root").is_dir()
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")
    assert not suite_conftest.usable_pytest_root(blocked)


def test_choose_temp_root_keeps_the_default_while_it_works(tmp_path):
    default, fallback = tmp_path / "default", tmp_path / "fallback"
    assert suite_conftest.choose_temp_root(default, fallback) is None
    assert not fallback.exists()
    user_root = default / f"pytest-of-{suite_conftest.suite_user()}"
    user_root.rmdir()
    user_root.write_text("blocked")
    assert suite_conftest.choose_temp_root(default, fallback) == fallback
    assert (fallback / user_root.name).is_dir()
    (fallback / user_root.name).rmdir()
    (fallback / user_root.name).write_text("blocked too")
    assert suite_conftest.choose_temp_root(default, fallback) is None


def test_explicit_basetemp_or_temproot_disables_the_fallback(monkeypatch):
    monkeypatch.delenv(suite_conftest.TEMPROOT_ENV, raising=False)
    config = SimpleNamespace(option=SimpleNamespace(basetemp="given"), stash={})
    suite_conftest.pytest_configure(config)
    assert suite_conftest.TEMPROOT_ENV not in os.environ and config.stash == {}
    monkeypatch.setenv(suite_conftest.TEMPROOT_ENV, "chosen-by-user")
    config = SimpleNamespace(option=SimpleNamespace(basetemp=None), stash={})
    suite_conftest.pytest_configure(config)
    assert os.environ[suite_conftest.TEMPROOT_ENV] == "chosen-by-user" and config.stash == {}
    assert suite_conftest.pytest_report_header(config) is None
