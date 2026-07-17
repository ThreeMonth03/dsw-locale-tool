"""Translation pull request scope validation tests."""

from __future__ import annotations

import shutil

import pytest
import yaml

from dsw_locale_tool.changes import validate_translation_pr
from dsw_locale_tool.errors import LocaleToolError
from tests.conftest import make_config


def _translation_tree(path):
    path.mkdir()
    (path / "translation-config.yml").write_text(
        yaml.safe_dump(make_config().model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (path / "translations" / "wizard").mkdir(parents=True)
    (path / "translations" / "wizard" / "save--000000000000.translation.md").write_text(
        "base\n", encoding="utf-8"
    )
    (path / "upstream").mkdir()
    (path / "upstream" / "wizard.po").write_text("immutable\n", encoding="utf-8")


def test_translation_pr_accepts_markdown_form_change(tmp_path):
    base = tmp_path / "base"
    head = tmp_path / "head"
    _translation_tree(base)
    shutil.copytree(base, head)
    unit = head / "translations" / "wizard" / "save--000000000000.translation.md"
    unit.write_text("translated\n", encoding="utf-8")

    report = validate_translation_pr(base, head, "sync/v4.32")

    assert report["changed_paths"] == ["translations/wizard/save--000000000000.translation.md"]
    assert report["translation_changed"] is True
    assert report["locale_version_bumped"] is False


def test_translation_pr_rejects_gettext_overlay(tmp_path):
    base = tmp_path / "base"
    head = tmp_path / "head"
    _translation_tree(base)
    shutil.copytree(base, head)
    (head / "overrides").mkdir()
    (head / "overrides" / "wizard.po").write_text("translated\n", encoding="utf-8")

    with pytest.raises(LocaleToolError, match="forbidden paths"):
        validate_translation_pr(base, head, "sync/v4.32")


def test_translation_pr_rejects_upstream_change(tmp_path):
    base = tmp_path / "base"
    head = tmp_path / "head"
    _translation_tree(base)
    shutil.copytree(base, head)
    (head / "upstream" / "wizard.po").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(LocaleToolError, match="forbidden paths"):
        validate_translation_pr(base, head, "sync/v4.32")


def test_translation_pr_accepts_only_target_version_bump(tmp_path):
    base = tmp_path / "base"
    head = tmp_path / "head"
    _translation_tree(base)
    shutil.copytree(base, head)
    config_path = head / "translation-config.yml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["versions"]["v4.32"]["locale_version"] = "4.32.1"
    config_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    report = validate_translation_pr(base, head, "sync/v4.32")

    assert report["locale_version_bumped"] is True
    assert report["translation_changed"] is False


def test_translation_pr_rejects_other_config_changes(tmp_path):
    base = tmp_path / "base"
    head = tmp_path / "head"
    _translation_tree(base)
    shutil.copytree(base, head)
    config_path = head / "translation-config.yml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["locale"]["organization_id"] = "other"
    config_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    with pytest.raises(LocaleToolError, match="may only bump locale_version"):
        validate_translation_pr(base, head, "sync/v4.32")
