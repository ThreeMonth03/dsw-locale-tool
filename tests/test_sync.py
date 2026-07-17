"""Upstream synchronization tests."""

from __future__ import annotations

import subprocess

import yaml

from dsw_locale_tool.sync import fetch_upstream_branch_heads, sync_upstream
from tests.conftest import make_config


def _git(repository, *arguments):
    subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )


def test_sync_copies_only_managed_baseline(tmp_path):
    upstream = tmp_path / "wizard-locales"
    upstream.mkdir()
    _git(upstream, "init", "--initial-branch", "v4.32")
    _git(upstream, "config", "user.name", "Test")
    _git(upstream, "config", "user.email", "test@example.test")

    (upstream / "locales" / "zh_Hant").mkdir(parents=True)
    (upstream / "wizard.pot").write_text("wizard template\n", encoding="utf-8")
    (upstream / "mail.pot").write_text("mail template\n", encoding="utf-8")
    for filename in ("wizard.po", "mail.po", "locale.json", "README.md"):
        (upstream / "locales" / "zh_Hant" / filename).write_text(f"{filename}\n", encoding="utf-8")
    _git(upstream, "add", ".")
    _git(upstream, "commit", "-m", "fixture")

    output = tmp_path / "translation"
    (output / "translations" / "wizard").mkdir(parents=True)
    local_file = output / "translations" / "wizard" / "local.translation.md"
    local_file.write_text("local content\n", encoding="utf-8")

    lock = sync_upstream(make_config(str(upstream)), "v4.32", output)

    assert (output / "upstream" / "wizard.pot").read_text(encoding="utf-8") == ("wizard template\n")
    assert local_file.read_text(encoding="utf-8") == "local content\n"
    lock_file = yaml.safe_load(
        (output / "upstream" / "upstream.lock.yml").read_text(encoding="utf-8")
    )
    assert lock_file["commit"] == lock["commit"]
    assert lock_file["version"] == "v4.32"


def test_fetch_upstream_branch_heads_returns_only_minor_release_branches(tmp_path):
    upstream = tmp_path / "wizard-locales"
    upstream.mkdir()
    _git(upstream, "init", "--initial-branch", "v4.32")
    _git(upstream, "config", "user.name", "Test")
    _git(upstream, "config", "user.email", "test@example.test")
    (upstream / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(upstream, "add", ".")
    _git(upstream, "commit", "-m", "fixture")
    _git(upstream, "branch", "v4.33")
    _git(upstream, "branch", "main")

    branches = fetch_upstream_branch_heads(str(upstream))

    assert sorted(branches) == ["v4.32", "v4.33"]
    assert all(len(commit) == 40 for commit in branches.values())
