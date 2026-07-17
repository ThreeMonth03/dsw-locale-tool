"""Catalog compatibility tests."""

from __future__ import annotations

import polib

from dsw_locale_tool.catalog import load_catalog, placeholder_mismatches


def test_load_catalog_tolerates_upstream_comment_without_space(tmp_path):
    catalog_path = tmp_path / "mail.pot"
    catalog_path.write_text(
        '#Comment from upstream\nmsgid ""\nmsgstr ""\n\nmsgid "Hello"\nmsgstr ""\n',
        encoding="utf-8",
    )

    catalog = load_catalog(catalog_path)

    assert catalog.find("Hello") is not None
    assert catalog_path.read_text(encoding="utf-8").startswith("#Comment")


def test_single_target_plural_form_may_use_placeholder_from_plural_source():
    entry = polib.POEntry(
        msgid="1 day",
        msgid_plural="%s days",
        msgstr_plural={0: "%s 天"},
    )

    assert placeholder_mismatches(entry) == []
