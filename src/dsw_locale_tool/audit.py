"""Audit translation coverage and Markdown translation-tree health."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from dsw_locale_tool.catalog import (
    catalog_index,
    entry_is_translated,
    load_catalog,
    placeholder_mismatches,
    translated_strings,
)
from dsw_locale_tool.translation_tree import (
    COMPONENTS,
    TranslationUnit,
    UnitKey,
    load_translation_tree,
)


def _entry_summary(entry: Any) -> dict[str, str | None]:
    return {"msgid": entry.msgid, "msgctxt": entry.msgctxt}


def _unit_summary(unit: TranslationUnit) -> dict[str, str | None]:
    return {"msgid": unit.msgid, "msgctxt": unit.msgctxt}


def _same_translation(unit: TranslationUnit, entry: Any) -> bool:
    return entry_is_translated(entry) and translated_strings(entry) == [unit.translation]


def _effective_entry(template_entry: Any, baseline_entry: Any, unit: TranslationUnit | None) -> Any:
    if unit is None or not unit.translation:
        return baseline_entry
    entry = copy.deepcopy(template_entry)
    entry.flags = [flag for flag in entry.flags if flag != "fuzzy"]
    entry.msgstr = "" if unit.msgid_plural else unit.translation
    entry.msgstr_plural = {"0": unit.translation} if unit.msgid_plural else {}
    return entry


def audit_component(
    root: Path,
    component: str,
    all_units: dict[UnitKey, TranslationUnit],
) -> dict[str, Any]:
    """Audit one gettext domain such as ``wizard`` or ``mail``."""
    template = load_catalog(root / "upstream" / f"{component}.pot")
    baseline = load_catalog(root / "upstream" / f"{component}.po")
    template_index = catalog_index(template)
    baseline_index = catalog_index(baseline)
    units = {key: unit for key, unit in all_units.items() if unit.component == component}

    effective: dict[tuple[str | None, str], Any] = {}
    missing: list[dict[str, str | None]] = []
    fuzzy: list[dict[str, str | None]] = []
    unscaffolded: list[dict[str, str | None]] = []
    for catalog_key, template_entry in template_index.items():
        unit_key: UnitKey = (component, *catalog_key)
        baseline_entry = baseline_index.get(catalog_key)
        unit = units.get(unit_key)
        candidate = _effective_entry(template_entry, baseline_entry, unit)
        effective[catalog_key] = candidate
        if not entry_is_translated(candidate):
            missing.append(_entry_summary(template_entry))
        if candidate is not None and "fuzzy" in candidate.flags:
            fuzzy.append(_entry_summary(template_entry))
        if not entry_is_translated(baseline_entry) and unit is None:
            unscaffolded.append(_entry_summary(template_entry))

    stale_translations = [
        _unit_summary(unit)
        for unit in units.values()
        if (unit.msgctxt, unit.msgid) not in template_index
    ]
    redundant_translations = [
        _unit_summary(unit)
        for unit in units.values()
        if unit.translation
        and (entry := baseline_index.get((unit.msgctxt, unit.msgid))) is not None
        and _same_translation(unit, entry)
    ]

    placeholder_issues: list[dict[str, object]] = []
    for entry in effective.values():
        if entry is not None and entry_is_translated(entry):
            placeholder_issues.extend(placeholder_mismatches(entry))
    completed = sum(bool(unit.translation) for unit in units.values())
    structure_issues = len(unscaffolded) + len(stale_translations) + len(redundant_translations)
    return {
        "counts": {
            "source_messages": len(template_index),
            "upstream_translated": sum(
                entry_is_translated(baseline_index.get(key)) for key in template_index
            ),
            "effective_translated": sum(
                entry_is_translated(effective.get(key)) for key in template_index
            ),
            "missing": len(missing),
            "fuzzy": len(fuzzy),
            "translation_units": len(units),
            "completed_units": completed,
            "blank_units": len(units) - completed,
            "unscaffolded": len(unscaffolded),
            "stale_translations": len(stale_translations),
            "redundant_translations": len(redundant_translations),
            "structure_issues": structure_issues,
            "placeholder_issues": len(placeholder_issues),
        },
        "missing": missing,
        "fuzzy": fuzzy,
        "unscaffolded": unscaffolded,
        "stale_translations": stale_translations,
        "redundant_translations": redundant_translations,
        "placeholder_issues": placeholder_issues,
    }


def audit_repository(root: str | Path) -> dict[str, Any]:
    """Audit both DSW gettext domains in a checked-out version branch."""
    repository_root = Path(root).resolve()
    units = load_translation_tree(repository_root)
    components = {
        component: audit_component(repository_root, component, units) for component in COMPONENTS
    }
    return {"schema_version": 1, "components": components}


def render_markdown(report: dict[str, Any]) -> str:
    """Render a concise human-readable audit report."""
    lines = [
        "# DSW locale audit",
        "",
        "| Component | Source | Upstream | Effective | Missing | Forms | Completed | "
        "Structure | Placeholders |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for component, details in report["components"].items():
        counts = details["counts"]
        lines.append(
            f"| {component} | {counts['source_messages']} | {counts['upstream_translated']} "
            f"| {counts['effective_translated']} | {counts['missing']} "
            f"| {counts['translation_units']} | {counts['completed_units']} "
            f"| {counts['structure_issues']} | {counts['placeholder_issues']} |"
        )

    labels = {
        "missing": "Missing or fuzzy translations",
        "unscaffolded": "Missing translation forms",
        "stale_translations": "Translated sources absent from upstream",
        "redundant_translations": "Local translations identical to upstream",
        "placeholder_issues": "Placeholder mismatches",
    }
    for component, details in report["components"].items():
        lines.extend(["", f"## {component}"])
        for key, label in labels.items():
            entries = details[key]
            lines.extend(["", f"### {label} ({len(entries)})", ""])
            if not entries:
                lines.append("None.")
                continue
            for entry in entries:
                context = f" [{entry['msgctxt']}]" if entry.get("msgctxt") else ""
                lines.append(f"- `{entry['msgid']}`{context}")

    return "\n".join(lines) + "\n"


def write_reports(report: dict[str, Any], output_directory: str | Path) -> tuple[Path, Path]:
    """Write deterministic JSON and Markdown reports."""
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "audit.json"
    markdown_path = output / "audit.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def failing_categories(report: dict[str, Any], categories: set[str]) -> list[str]:
    """Return requested failure categories that contain at least one finding."""
    count_keys = {
        "missing": "missing",
        "placeholders": "placeholder_issues",
        "structure": "structure_issues",
    }
    failures: list[str] = []
    for category in ("missing", "placeholders", "structure"):
        if category not in categories:
            continue
        count_key = count_keys[category]
        if any(details["counts"][count_key] > 0 for details in report["components"].values()):
            failures.append(category)
    return failures
