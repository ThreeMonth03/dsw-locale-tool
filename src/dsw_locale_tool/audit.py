"""Audit translation coverage and local overlay health."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dsw_locale_tool.catalog import (
    catalog_index,
    entry_is_translated,
    load_catalog,
    merge_catalogs,
    placeholder_mismatches,
    translated_strings,
)

COMPONENTS = ("wizard", "mail")


def _entry_summary(entry: Any) -> dict[str, str | None]:
    return {"msgid": entry.msgid, "msgctxt": entry.msgctxt}


def _same_translation(left: Any, right: Any) -> bool:
    return translated_strings(left) == translated_strings(right) and left.flags == right.flags


def audit_component(root: Path, component: str) -> dict[str, Any]:
    """Audit one gettext domain such as ``wizard`` or ``mail``."""
    template = load_catalog(root / "upstream" / f"{component}.pot")
    baseline = load_catalog(root / "upstream" / f"{component}.po")
    overrides = load_catalog(root / "overrides" / f"{component}.po", required=False)
    extras = load_catalog(root / "extras" / f"{component}.po", required=False)
    effective = merge_catalogs(
        root / "upstream" / f"{component}.po",
        root / "overrides" / f"{component}.po",
        root / "extras" / f"{component}.po",
    )

    template_index = catalog_index(template)
    baseline_index = catalog_index(baseline)
    override_index = catalog_index(overrides)
    extras_index = catalog_index(extras)
    effective_index = catalog_index(effective)

    missing = [
        _entry_summary(entry)
        for key, entry in template_index.items()
        if not entry_is_translated(effective_index.get(key))
    ]
    fuzzy = [
        _entry_summary(entry)
        for key, entry in template_index.items()
        if (candidate := effective_index.get(key)) is not None and "fuzzy" in candidate.flags
    ]
    misplaced_overrides = [
        _entry_summary(entry) for key, entry in override_index.items() if key not in template_index
    ]
    extras_now_upstream = [
        _entry_summary(entry) for key, entry in extras_index.items() if key in template_index
    ]
    redundant_overrides = [
        _entry_summary(entry)
        for key, entry in override_index.items()
        if (upstream_entry := baseline_index.get(key)) is not None
        and _same_translation(entry, upstream_entry)
    ]

    placeholder_issues: list[dict[str, object]] = []
    relevant_keys = set(template_index) | set(extras_index)
    for key in relevant_keys:
        entry = effective_index.get(key)
        if entry is not None and entry_is_translated(entry):
            placeholder_issues.extend(placeholder_mismatches(entry))

    return {
        "counts": {
            "source_messages": len(template_index),
            "upstream_translated": sum(
                entry_is_translated(baseline_index.get(key)) for key in template_index
            ),
            "effective_translated": sum(
                entry_is_translated(effective_index.get(key)) for key in template_index
            ),
            "missing": len(missing),
            "fuzzy": len(fuzzy),
            "overrides": len(override_index),
            "extras": len(extras_index),
            "extras_now_upstream": len(extras_now_upstream),
            "misplaced_overrides": len(misplaced_overrides),
            "redundant_overrides": len(redundant_overrides),
            "placeholder_issues": len(placeholder_issues),
        },
        "missing": missing,
        "fuzzy": fuzzy,
        "extras_now_upstream": extras_now_upstream,
        "misplaced_overrides": misplaced_overrides,
        "redundant_overrides": redundant_overrides,
        "placeholder_issues": placeholder_issues,
    }


def audit_repository(root: str | Path) -> dict[str, Any]:
    """Audit both DSW gettext domains in a checked-out version branch."""
    repository_root = Path(root).resolve()
    components = {
        component: audit_component(repository_root, component) for component in COMPONENTS
    }
    return {"schema_version": 1, "components": components}


def render_markdown(report: dict[str, Any]) -> str:
    """Render a concise human-readable audit report."""
    lines = [
        "# DSW locale audit",
        "",
        "| Component | Source | Upstream translated | Effective translated | Missing | "
        "Extras | Placeholder issues |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for component, details in report["components"].items():
        counts = details["counts"]
        lines.append(
            f"| {component} | {counts['source_messages']} | {counts['upstream_translated']} "
            f"| {counts['effective_translated']} | {counts['missing']} | {counts['extras']} "
            f"| {counts['placeholder_issues']} |"
        )

    labels = {
        "missing": "Missing or fuzzy translations",
        "extras_now_upstream": "Extras now available upstream",
        "misplaced_overrides": "Overrides absent from the upstream POT",
        "redundant_overrides": "Overrides identical to upstream",
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
        "structure": "misplaced_overrides",
    }
    failures: list[str] = []
    for category in ("missing", "placeholders", "structure"):
        if category not in categories:
            continue
        count_key = count_keys[category]
        if any(details["counts"][count_key] > 0 for details in report["components"].values()):
            failures.append(category)
    return failures
