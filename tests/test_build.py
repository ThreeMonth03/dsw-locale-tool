"""Locale source build tests."""

from __future__ import annotations

import json

import polib

from dsw_locale_tool.build import build_source
from tests.conftest import make_config, make_translation_tree


def test_build_source_merges_layers_and_rewrites_metadata(tmp_path):
    repository = tmp_path / "repository"
    make_translation_tree(repository)
    (repository / "locale").mkdir()
    (repository / "locale" / "README.md").write_text("# Locale\n", encoding="utf-8")
    output = tmp_path / "build" / "locale"

    build_source(make_config(), "v4.32", repository, output)

    wizard = polib.pofile(output / "wizard.po")
    assert wizard.find("Count: %s").msgstr == "數量"
    assert wizard.find("Runtime only").msgstr == "僅執行階段出現"
    assert json.loads((output / "locale.json").read_text(encoding="utf-8")) == {
        "organizationId": "depositar",
        "localeId": "zh_Hant",
        "version": "4.32.0",
        "code": "zh-hant",
        "recommendedAppVersion": "4.32.0",
        "name": "繁體中文（測試）",
        "description": "測試語系",
        "license": "CC-BY-4.0",
    }
    assert (output / "README.md").read_text(encoding="utf-8") == "# Locale\n"
