"""Automated DSW release reconciliation tests."""

from __future__ import annotations

import yaml

from dsw_locale_tool.reconcile import reconcile_version_config, render_reconcile_report
from dsw_locale_tool.versions import WeblateVersion
from tests.conftest import make_config


def _official(version: str, *, locked: bool = False) -> WeblateVersion:
    number = version.removeprefix("v")
    return WeblateVersion(
        version=version,
        project=f"DSW {number}",
        slug=f"dsw-{number.replace('.', '-')}",
        locked=locked,
        url=f"https://localize.ds-wizard.org/projects/dsw-{number.replace('.', '-')}/",
    )


def _write_config(path, config=None):
    value = config or make_config()
    path.write_text(
        yaml.safe_dump(value.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def test_reconcile_adds_version_only_after_upstream_branch_exists(tmp_path):
    path = tmp_path / "translation-config.yml"
    _write_config(path)

    report = reconcile_version_config(
        path,
        [_official("v4.32", locked=True), _official("v4.33")],
        {"v4.32": "1" * 40, "v4.33": "2" * 40},
    )

    saved = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert saved["versions"]["v4.32"]["state"] == "maintenance"
    assert saved["versions"]["v4.33"] == {
        "upstream_ref": "v4.33",
        "state": "active",
    }
    assert report["changed"] is True
    assert report["managed_versions"] == ["v4.32", "v4.33"]
    assert report["added_versions"][0]["upstream_commit"] == "2" * 40


def test_reconcile_waits_for_missing_upstream_branch(tmp_path):
    path = tmp_path / "translation-config.yml"
    _write_config(path)
    before = path.read_text(encoding="utf-8")

    report = reconcile_version_config(path, [_official("v4.33")], {})

    assert path.read_text(encoding="utf-8") == before
    assert report["changed"] is False
    assert report["pending_versions"] == [
        {
            "version": "v4.33",
            "upstream_ref": "v4.33",
            "reason": "upstream branch is not available",
        }
    ]


def test_reconcile_preserves_versions_absent_from_weblate(tmp_path):
    path = tmp_path / "translation-config.yml"
    _write_config(path)

    report = reconcile_version_config(path, [], {})

    assert report["changed"] is False
    assert report["preserved_versions"] == ["v4.32"]
    assert report["managed_versions"] == ["v4.32"]
    assert "Versions absent from Weblate were preserved" in render_reconcile_report(report)
