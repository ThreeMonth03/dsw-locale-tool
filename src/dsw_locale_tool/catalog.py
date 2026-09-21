"""PO catalog inspection shared by synchronization and contribution checks."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import TypeAlias

import polib

from dsw_locale_tool.errors import LocaleToolError

CatalogKey: TypeAlias = tuple[str | None, str]

PRINTF_PLACEHOLDER = re.compile(
    r"%(?!%)(?:\([^)]+\))?[#0 +'\-]*(?:\d+|\*)?(?:\.\d+|\.\*)?"
    r"(?:hh|h|ll|l|L|z|j|t)?[diouxXeEfFgGcrsa]"
)
BRACE_PLACEHOLDER = re.compile(r"(?<!\{)\{[A-Za-z_][A-Za-z0-9_.:-]*\}(?!\})")
DOLLAR_PLACEHOLDER = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_.:-]*\}")
MALFORMED_TRANSLATOR_COMMENT = re.compile(r"^#(?=[^\s.,:|~])", re.MULTILINE)


def load_catalog(path: Path) -> polib.POFile:
    """Load a required PO or POT catalog."""
    if not path.is_file():
        raise LocaleToolError(f"Required catalog does not exist: {path}")
    try:
        content = path.read_text(encoding="utf-8")
        # Accept gettext translator comments without a space while preserving
        # the downloaded catalog byte-for-byte on disk.
        normalized = MALFORMED_TRANSLATOR_COMMENT.sub("# ", content)
        return polib.pofile(normalized)
    except (OSError, UnicodeError, ValueError) as error:
        raise LocaleToolError(f"Unable to parse catalog {path}: {error}") from error


def entry_key(entry: polib.POEntry) -> CatalogKey:
    """Return the stable gettext identity used for joins."""
    return entry.msgctxt, entry.msgid


def catalog_index(catalog: polib.POFile) -> dict[CatalogKey, polib.POEntry]:
    """Index non-obsolete entries by context and source string."""
    index = {}
    for entry in catalog:
        if entry.obsolete:
            continue
        key = entry_key(entry)
        if key in index:
            raise LocaleToolError(f"Duplicate gettext source identity: {key!r}")
        index[key] = entry
    return index


def translated_strings(entry: polib.POEntry) -> list[str]:
    """Return all singular or plural translated strings."""
    if entry.msgid_plural:
        return list(entry.msgstr_plural.values())
    return [entry.msgstr]


def source_strings(entry: polib.POEntry) -> list[str]:
    """Return source strings aligned with singular/plural translations."""
    if entry.msgid_plural:
        return [entry.msgid, entry.msgid_plural]
    return [entry.msgid]


def placeholder_counter(text: str) -> Counter[str]:
    """Extract placeholders whose omission can break a rendered UI string."""
    placeholders = (
        PRINTF_PLACEHOLDER.findall(text)
        + BRACE_PLACEHOLDER.findall(text)
        + DOLLAR_PLACEHOLDER.findall(text)
    )
    return Counter(placeholders)


def placeholder_mismatches(entry: polib.POEntry) -> list[dict[str, object]]:
    """Compare placeholders in an entry's source and translated forms."""
    sources = source_strings(entry)
    translations = translated_strings(entry)

    expected_counters: list[Counter[str]]
    if len(sources) == 2 and len(translations) == 1:
        # Languages such as zh_Hant have one plural form. DSW's English singular
        # sometimes hard-codes "1" while its plural uses ``%s``; the one target
        # form must then be allowed to preserve placeholders from either source.
        combined = placeholder_counter(sources[0]) | placeholder_counter(sources[1])
        expected_counters = [combined]
    elif len(sources) == 1:
        expected_counters = [placeholder_counter(sources[0])] * len(translations)
    else:
        expected_counters = [
            placeholder_counter(sources[min(index, len(sources) - 1)])
            for index in range(len(translations))
        ]

    issues: list[dict[str, object]] = []
    for expected, translation in zip(expected_counters, translations, strict=True):
        actual = placeholder_counter(translation)
        if expected != actual:
            issues.append(
                {
                    "msgid": entry.msgid,
                    "msgctxt": entry.msgctxt,
                    "expected": dict(expected),
                    "actual": dict(actual),
                }
            )
    return issues
