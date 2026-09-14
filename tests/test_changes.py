"""Translation pull request scope validation tests."""

from __future__ import annotations

import shutil
from dataclasses import replace

import pytest
import yaml

from dsw_locale_tool.changes import validate_translation_pr
from dsw_locale_tool.errors import LocaleToolError
from dsw_locale_tool.translation_tree import (
    TranslationUnit,
    render_translation_unit,
    unit_relative_path,
)
from tests.conftest import make_config, make_translation_tree

BLANK = TranslationUnit("wizard", "message", "Still missing")


def _translation_tree(path):
    make_translation_tree(path)
    (path / "translation-config.yml").write_text(
        yaml.safe_dump(make_config().model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def test_translation_pr_accepts_markdown_form_change(tmp_path):
    base = tmp_path / "base"
    head = tmp_path / "head"
    _translation_tree(base)
    shutil.copytree(base, head)
    unit = head / unit_relative_path(BLANK)
    unit.write_text(
        render_translation_unit(replace(BLANK, translation="尚未翻譯")), encoding="utf-8"
    )

    report = validate_translation_pr(base, head, "sync/v4.32")

    assert report["changed_paths"] == [unit_relative_path(BLANK).as_posix()]
    assert report["translation_changed"] is True
    assert report["locale_version_bumped"] is False

    unit.write_text(
        render_translation_unit(replace(BLANK, translation="審核後的譯文")), encoding="utf-8"
    )
    assert validate_translation_pr(base, head, "sync/v4.32")["valid"]


@pytest.mark.parametrize("translation", ["改寫", ""])
def test_accepts_changing_or_clearing_existing_translation(tmp_path, translation):
    base, head = tmp_path / "base", tmp_path / "head"
    _translation_tree(base)
    shutil.copytree(base, head)
    completed = TranslationUnit("wizard", "message", "Count: %s", translation)
    (head / unit_relative_path(completed)).write_text(
        render_translation_unit(completed), encoding="utf-8"
    )
    assert validate_translation_pr(base, head, "sync/v4.32")["translation_changed"]


def test_accepts_reviewing_fuzzy_official_translation(tmp_path):
    from dsw_locale_tool.catalog import load_catalog

    base, head = tmp_path / "base", tmp_path / "head"
    _translation_tree(base)
    catalog = load_catalog(base / "upstream/wizard.po")
    entry = catalog.find(BLANK.msgid)
    entry.msgstr = "既有譯文"
    entry.flags = ["fuzzy"]
    catalog.save(base / "upstream/wizard.po")
    shutil.copytree(base, head)
    (head / unit_relative_path(BLANK)).write_text(
        render_translation_unit(replace(BLANK, translation="覆蓋")), encoding="utf-8"
    )
    assert validate_translation_pr(base, head, "sync/v4.32")["translation_changed"]


def test_accepts_new_correction_form_for_translated_official_entry(tmp_path):
    base, head = tmp_path / "base", tmp_path / "head"
    _translation_tree(base)
    shutil.copytree(base, head)
    correction = TranslationUnit("wizard", "message", "Hello", "你好")
    (head / unit_relative_path(correction)).write_text(
        render_translation_unit(correction), encoding="utf-8"
    )
    assert validate_translation_pr(base, head, "sync/v4.32")["translation_changed"]


@pytest.mark.parametrize("identity", [{"msgctxt": "wrong"}, {"msgid_plural": "Hello plural"}])
def test_rejects_new_correction_with_wrong_source_identity(tmp_path, identity):
    base, head = tmp_path / "base", tmp_path / "head"
    _translation_tree(base)
    shutil.copytree(base, head)
    correction = TranslationUnit("wizard", "message", "Hello", "你好", **identity)
    (head / unit_relative_path(correction)).write_text(
        render_translation_unit(correction), encoding="utf-8"
    )
    with pytest.raises(LocaleToolError, match="must match an official POT entry"):
        validate_translation_pr(base, head, "sync/v4.32")


@pytest.mark.parametrize("operation", ["delete", "add", "source"])
def test_rejects_changed_form_identity(tmp_path, operation):
    base, head = tmp_path / "base", tmp_path / "head"
    _translation_tree(base)
    shutil.copytree(base, head)
    path = head / unit_relative_path(BLANK)
    if operation == "delete":
        path.unlink()
    elif operation == "add":
        new = replace(BLANK, msgid="Unknown")
        (head / unit_relative_path(new)).write_text(render_translation_unit(new), encoding="utf-8")
    else:
        path.write_text(render_translation_unit(replace(BLANK, msgid="Changed")), encoding="utf-8")
    with pytest.raises(LocaleToolError):
        validate_translation_pr(base, head, "sync/v4.32")


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
