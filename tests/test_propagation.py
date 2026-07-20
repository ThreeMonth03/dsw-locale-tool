"""Exact cross-version translation propagation tests."""

from __future__ import annotations

from dataclasses import replace

from dsw_locale_tool.propagation import propagate_translations, write_propagation_report
from dsw_locale_tool.translation_tree import (
    TranslationUnit,
    load_translation_tree,
    write_translation_tree,
)
from tests.conftest import make_translation_tree


def _blank_completed_forms(root):
    units = load_translation_tree(root)
    write_translation_tree(
        root,
        {key: replace(unit, translation="") for key, unit in units.items()},
    )


def _translation_files(root):
    return {
        path.relative_to(root): path.read_bytes()
        for path in (root / "translations").rglob("*")
        if path.is_file()
    }


def test_propagates_only_completed_exact_sources(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    make_translation_tree(source)
    make_translation_tree(target)
    _blank_completed_forms(target)

    report = propagate_translations(source, target)

    target_units = load_translation_tree(target)
    assert target_units[("wizard", None, "Count: %s")].translation == "數量"
    assert report["counts"] == {
        "source_completed": 1,
        "target_blank_before": 2,
        "applied": 1,
    }


def test_does_not_overwrite_completed_target(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    make_translation_tree(source)
    make_translation_tree(target)
    units = load_translation_tree(target)
    count_key = ("wizard", None, "Count: %s")
    units[count_key] = replace(units[count_key], translation="目標版本用語")
    write_translation_tree(target, units)

    report = propagate_translations(source, target)

    assert load_translation_tree(target)[count_key].translation == "目標版本用語"
    assert report["counts"]["applied"] == 0


def test_requires_complete_source_identity(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    make_translation_tree(source)
    make_translation_tree(target)
    source_units = load_translation_tree(source)
    target_units = load_translation_tree(target)
    source_unit = TranslationUnit(
        "wizard", "message", "Context-sensitive", "來源翻譯", msgctxt="source-context"
    )
    target_unit = TranslationUnit(
        "wizard", "message", "Context-sensitive", "", msgctxt="target-context"
    )
    source_units[source_unit.key] = source_unit
    target_units[target_unit.key] = target_unit
    write_translation_tree(source, source_units)
    write_translation_tree(target, target_units)

    before = _translation_files(target)
    report = propagate_translations(source, target)
    after = _translation_files(target)

    assert report["counts"]["applied"] == 0
    assert before == after


def test_writes_json_and_markdown_reports(tmp_path):
    report = {
        "schema_version": 1,
        "counts": {"source_completed": 1, "target_blank_before": 1, "applied": 0},
        "applied": [],
    }

    json_path, markdown_path = write_propagation_report(report, tmp_path / "reports")

    assert '"applied": 0' in json_path.read_text(encoding="utf-8")
    assert "Translations applied: 0" in markdown_path.read_text(encoding="utf-8")
