"""Validate local contributions and report official coverage separately."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polib

from dsw_locale_tool.catalog import (
    catalog_index,
    load_catalog,
    placeholder_mismatches,
    translated_strings,
)
from dsw_locale_tool.translation_tree import COMPONENTS, load_translation_tree


def audit_repository(root: str | Path) -> dict[str, Any]:
    """Official errors are diagnostics; only contribution errors block CI."""
    root = Path(root)
    units = load_translation_tree(root)
    components = {}
    for component in COMPONENTS:
        template = catalog_index(load_catalog(root / "upstream" / f"{component}.pot"))
        baseline = catalog_index(load_catalog(root / "upstream" / f"{component}.po"))
        local = [unit for unit in units.values() if unit.component == component]
        structure = []
        placeholders = []
        for unit in local:
            source = template.get((unit.msgctxt, unit.msgid))
            if source is None or (source.msgid_plural or None) != unit.msgid_plural:
                structure.append({"msgid": unit.msgid, "msgctxt": unit.msgctxt})
            if unit.translation:
                entry = polib.POEntry(
                    msgid=unit.msgid,
                    msgctxt=unit.msgctxt,
                    msgid_plural=unit.msgid_plural or "",
                    msgstr="" if unit.msgid_plural else unit.translation,
                    msgstr_plural={0: unit.translation} if unit.msgid_plural else {},
                )
                placeholders.extend(placeholder_mismatches(entry))
        components[component] = {
            "counts": {
                "source_messages": len(template),
                "empty": sum(not any(translated_strings(e)) for e in baseline.values()),
                "fuzzy": sum("fuzzy" in e.flags for e in baseline.values()),
                "local_filled": sum(bool(u.translation) for u in local),
                "local_blank": sum(not u.translation for u in local),
                "structure_issues": len(structure),
                "placeholder_issues": len(placeholders),
            },
            "structure_issues": structure,
            "placeholder_issues": placeholders,
            "upstream_placeholder_issues": [
                issue
                for entry in baseline.values()
                if any(translated_strings(entry))
                for issue in placeholder_mismatches(entry)
            ],
        }
    return {"schema_version": 1, "components": components}


def failing_categories(report: dict[str, Any], categories: set[str]) -> list[str]:
    return [
        category
        for category, key in (
            ("structure", "structure_issues"),
            ("placeholders", "placeholder_issues"),
        )
        if category in categories and any(data[key] for data in report["components"].values())
    ]


def write_reports(report: dict[str, Any], output_directory: str | Path) -> tuple[Path, Path]:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    json_path, markdown_path = output / "audit.json", output / "audit.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Translation checks",
        "",
        "| Component | Official empty | Official fuzzy | Local filled | Local errors |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, data in report["components"].items():
        counts = data["counts"]
        lines.append(
            f"| {name} | {counts['empty']} | {counts['fuzzy']} | {counts['local_filled']} | "
            f"{counts['structure_issues'] + counts['placeholder_issues']} |"
        )
        for key in ("structure_issues", "placeholder_issues", "upstream_placeholder_issues"):
            if data[key]:
                lines.extend(["", f"## {name}: {key.replace('_', ' ')}", ""])
                for issue in data[key]:
                    lines.append("- " + json.dumps(issue, ensure_ascii=False))
    lines.extend(
        [
            "",
            "Official translation findings are reported without blocking unrelated contributions.",
            "",
        ]
    )
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, markdown_path
