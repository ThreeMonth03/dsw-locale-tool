"""Shared test helpers."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import polib
import yaml

from dsw_locale_tool.config import TranslationConfig
from dsw_locale_tool.translation_tree import (
    load_translation_tree,
    refresh_translation_tree,
    write_translation_tree,
)


def make_catalog(path: Path, entries: list[dict[str, Any]]) -> None:
    """Write a minimal UTF-8 PO or POT catalog."""
    path.parent.mkdir(parents=True, exist_ok=True)
    catalog = polib.POFile()
    catalog.metadata = {
        "Content-Type": "text/plain; charset=UTF-8",
        "Language": "zh_Hant",
        "Plural-Forms": "nplurals=1; plural=0;",
    }
    for values in entries:
        catalog.append(polib.POEntry(**values))
    catalog.save(path)


def make_config(repository: str = "https://example.test/wizard-locales.git") -> TranslationConfig:
    """Build a representative valid configuration."""
    return TranslationConfig.model_validate(
        {
            "schema_version": 1,
            "locale": {
                "organization_id": "depositar",
                "locale_id": "zh_Hant",
                "code": "zh-hant",
                "name": "繁體中文（測試）",
                "description": "測試語系",
                "license": "CC-BY-4.0",
            },
            "upstream": {"repository": repository, "locale": "zh_Hant"},
            "versions": {
                "v4.32": {
                    "upstream_ref": "v4.32",
                    "locale_version": "4.32.0",
                    "recommended_app_version": "4.32.0",
                    "state": "active",
                }
            },
        }
    )


def make_translation_tree(root: Path) -> None:
    """Create an official baseline and representative Markdown translations."""
    make_catalog(
        root / "upstream" / "wizard.pot",
        [
            {"msgid": "Hello", "msgstr": ""},
            {"msgid": "Count: %s", "msgstr": ""},
            {"msgid": "Still missing", "msgstr": ""},
        ],
    )
    make_catalog(
        root / "upstream" / "wizard.po",
        [
            {"msgid": "Hello", "msgstr": "您好"},
            {"msgid": "Count: %s", "msgstr": ""},
            {"msgid": "Still missing", "msgstr": ""},
        ],
    )
    make_catalog(
        root / "upstream" / "mail.pot",
        [{"msgid": "Reset password", "msgstr": ""}],
    )
    make_catalog(
        root / "upstream" / "mail.po",
        [{"msgid": "Reset password", "msgstr": "重設密碼"}],
    )
    (root / "upstream" / "upstream.lock.yml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "repository": "https://example.test/wizard-locales.git",
                "ref": "v4.32",
                "commit": "0" * 40,
                "locale": "zh_Hant",
                "version": "v4.32",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    refresh_translation_tree(root)
    units = load_translation_tree(root)
    count_key = ("wizard", None, "Count: %s")
    units[count_key] = replace(units[count_key], translation="數量")
    write_translation_tree(root, units)
