"""Markdown translation-tree tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from dsw_locale_tool.errors import LocaleToolError
from dsw_locale_tool.translation_tree import (
    TranslationUnit,
    load_translation_tree,
    parse_translation_unit,
    refresh_translation_tree,
    render_translation_unit,
    unit_relative_path,
)
from tests.conftest import make_catalog, make_translation_tree


def test_translation_unit_round_trip_preserves_multiline_source_and_fences(tmp_path):
    unit = TranslationUnit(
        component="wizard",
        kind="message",
        msgid="Use ~~~ here\nand keep this newline\n",
        msgid_plural="Use ~~~~ in plurals",
        msgctxt="toolbar",
        translation="使用 ~~ 符號",
    )
    path = tmp_path / unit_relative_path(unit)
    path.parent.mkdir(parents=True)
    path.write_text(render_translation_unit(unit), encoding="utf-8")

    assert parse_translation_unit(path, tmp_path) == unit
    assert "~~~~~text" in path.read_text(encoding="utf-8")


def test_translation_unit_rejects_source_edits(tmp_path):
    unit = TranslationUnit(component="wizard", kind="message", msgid="Save")
    path = tmp_path / unit_relative_path(unit)
    path.parent.mkdir(parents=True)
    path.write_text(
        render_translation_unit(unit).replace("\nSave\n", "\nSave now\n"),
        encoding="utf-8",
    )

    with pytest.raises(LocaleToolError, match="source or identity was modified"):
        parse_translation_unit(path, tmp_path)


def test_refresh_scaffolds_only_official_gaps(tmp_path):
    make_translation_tree(tmp_path)

    result = refresh_translation_tree(tmp_path)
    units = load_translation_tree(tmp_path)

    assert result == {"units": 2, "completed": 1, "blank": 1}
    assert ("wizard", None, "Hello") not in units
    assert units[("wizard", None, "Still missing")].translation == ""
    index = (tmp_path / "translations" / "README.md").read_text(encoding="utf-8")
    assert "### Open (1)" in index
    assert "### Completed (1)" in index
    assert index.index("Still missing") < index.index("Count: %s")


def test_refresh_removes_translation_once_upstream_matches(tmp_path):
    make_translation_tree(tmp_path)
    wizard_path = tmp_path / "upstream" / "wizard.po"
    make_catalog(
        wizard_path,
        [
            {"msgid": "Hello", "msgstr": "您好"},
            {"msgid": "Count: %s", "msgstr": "數量"},
            {"msgid": "Still missing", "msgstr": ""},
        ],
    )

    refresh_translation_tree(tmp_path)

    assert ("wizard", None, "Count: %s") not in load_translation_tree(tmp_path)


def test_refresh_repairs_generated_index(tmp_path):
    make_translation_tree(tmp_path)
    index = tmp_path / "translations" / "README.md"
    index.write_text("# Stale generated index\n", encoding="utf-8")

    refresh_translation_tree(tmp_path)

    assert "### Open (1)" in index.read_text(encoding="utf-8")
    load_translation_tree(tmp_path)


def test_refresh_index_is_stable_for_sources_differing_only_in_case(tmp_path):
    messages = [
        {"msgid": "Migrate Project", "msgstr": ""},
        {"msgid": "Migrate project", "msgstr": ""},
    ]
    for filename in ("wizard.pot", "wizard.po"):
        make_catalog(tmp_path / "upstream" / filename, messages)
    for filename in ("mail.pot", "mail.po"):
        make_catalog(tmp_path / "upstream" / filename, [])

    refresh_translation_tree(tmp_path)
    index = (tmp_path / "translations/README.md").read_bytes()
    assert len(load_translation_tree(tmp_path)) == 2
    refresh_translation_tree(tmp_path)
    assert (tmp_path / "translations/README.md").read_bytes() == index
    make_catalog(tmp_path / "upstream/wizard.pot", list(reversed(messages)))
    refresh_translation_tree(tmp_path)
    assert (tmp_path / "translations/README.md").read_bytes() == index


def test_refresh_refuses_to_discard_translation_removed_upstream(tmp_path):
    make_translation_tree(tmp_path)
    make_catalog(
        tmp_path / "upstream" / "wizard.pot",
        [
            {"msgid": "Hello", "msgstr": ""},
            {"msgid": "Still missing", "msgstr": ""},
        ],
    )

    with pytest.raises(LocaleToolError, match="no longer exists upstream"):
        refresh_translation_tree(tmp_path)


def test_translation_edit_does_not_change_unit_path():
    unit = TranslationUnit(component="mail", kind="message", msgid="Reset password")

    assert unit_relative_path(unit) == unit_relative_path(replace(unit, translation="重設密碼"))


def test_matching_fuzzy_draft_is_removed_without_changing_official_state(tmp_path):
    from dsw_locale_tool.catalog import load_catalog

    make_translation_tree(tmp_path)
    path = tmp_path / "upstream/wizard.po"
    catalog = load_catalog(path)
    catalog.find("Count: %s").msgstr = "數量"
    catalog.find("Count: %s").flags = ["fuzzy"]
    catalog.save(path)
    before = path.read_bytes()
    refresh_translation_tree(tmp_path)
    assert ("wizard", None, "Count: %s") not in load_translation_tree(tmp_path)
    assert path.read_bytes() == before


def test_nonempty_fuzzy_has_no_blank_translation_form(tmp_path):
    from dsw_locale_tool.catalog import load_catalog

    make_translation_tree(tmp_path)
    path = tmp_path / "upstream/wizard.po"
    catalog = load_catalog(path)
    catalog.find("Still missing").msgstr = "待審譯文"
    catalog.find("Still missing").flags = ["fuzzy"]
    catalog.save(path)
    refresh_translation_tree(tmp_path)
    assert ("wizard", None, "Still missing") not in load_translation_tree(tmp_path)
