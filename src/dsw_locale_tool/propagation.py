"""Propagate exact translations between maintained DSW release lines."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from dsw_locale_tool.translation_tree import (
    TranslationUnit,
    load_translation_tree,
    source_hash,
    unit_relative_path,
    upstream_translated_keys,
    write_translation_tree,
)


def propagate_translations(
    source_root: str | Path,
    target_root: str | Path,
) -> dict[str, Any]:
    """Fill blank target forms whose complete source identity exists in the source tree."""
    source_units = load_translation_tree(source_root)
    target_units = load_translation_tree(target_root)
    protected = upstream_translated_keys(target_root)
    completed_sources = {
        source_hash(unit): unit for unit in source_units.values() if unit.translation
    }
    updated = dict(target_units)
    applied: list[dict[str, str | None]] = []

    for key, target in sorted(
        target_units.items(), key=lambda item: unit_relative_path(item[1]).as_posix()
    ):
        if target.translation or key in protected:
            continue
        source = completed_sources.get(source_hash(target))
        if source is None:
            continue
        updated[key] = replace(target, translation=source.translation)
        applied.append(_applied_entry(target, source))

    if applied:
        write_translation_tree(target_root, updated)

    return {
        "schema_version": 1,
        "counts": {
            "source_completed": len(completed_sources),
            "target_blank_before": sum(not unit.translation for unit in target_units.values()),
            "applied": len(applied),
        },
        "applied": applied,
    }


def _applied_entry(target: TranslationUnit, source: TranslationUnit) -> dict[str, str | None]:
    return {
        "path": unit_relative_path(target).as_posix(),
        "component": target.component,
        "kind": target.kind,
        "source": target.msgid,
        "context": target.msgctxt,
        "translation": source.translation,
    }


def write_propagation_report(
    report: dict[str, Any], report_directory: str | Path
) -> tuple[Path, Path]:
    """Write deterministic machine-readable and human-readable propagation reports."""
    directory = Path(report_directory)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "propagation.json"
    markdown_path = directory / "propagation.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    counts = report["counts"]
    lines = [
        "# Exact translation propagation",
        "",
        f"- Completed source forms: {counts['source_completed']}",
        f"- Blank target forms before propagation: {counts['target_blank_before']}",
        f"- Translations applied: {counts['applied']}",
    ]
    if report["applied"]:
        lines.extend(["", "## Applied translations", ""])
        for entry in report["applied"]:
            label = str(entry["source"]).replace("\n", " ")
            lines.append(f"- `{entry['path']}` — {label}")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, markdown_path
