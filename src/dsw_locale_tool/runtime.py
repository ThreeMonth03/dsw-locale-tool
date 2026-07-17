"""Classify visible English text captured from a running DSW client."""

from __future__ import annotations

import html
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from dsw_locale_tool.catalog import (
    catalog_index,
    entry_is_translated,
    load_catalog,
    merge_catalogs,
    source_strings,
)
from dsw_locale_tool.errors import LocaleToolError

CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
LATIN_WORD_PATTERN = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
MARKDOWN_MARKER_PATTERN = re.compile(r"[*_`~#]+")
IDENTIFIER_PATTERN = re.compile(
    r"^(?:https?://|[\w.+-]+@[\w.-]+\.|[0-9a-f]{8}-[0-9a-f-]{27}|"
    r"v?\d+(?:\.\d+)+|[a-z]{2,3}(?:[-_][A-Za-z0-9]+)+$|"
    r"[A-Za-z0-9_~-]+(?::[A-Za-z0-9_.-]+){2,}$|"
    r"[a-z0-9_.-]+/[a-z0-9_.-]+$)",
    re.IGNORECASE,
)

BUILTIN_ALLOWED_TEXT = {
    "API",
    "DOI",
    "DSW",
    "DS Wizard",
    "Data Stewardship Wizard",
    "Default English locale for Wizard UI",
    "English",
    "OpenID",
    "ORCID",
    "URL",
    "UUID",
}


def normalize_runtime_text(value: str) -> str:
    """Collapse browser whitespace into one stable comparison form."""
    return " ".join(value.replace("\u00a0", " ").split())


def _visible_text_variant(value: str) -> str:
    unescaped = html.unescape(value)
    without_html = HTML_TAG_PATTERN.sub(" ", unescaped)
    without_markdown = MARKDOWN_MARKER_PATTERN.sub("", without_html)
    return normalize_runtime_text(without_markdown)


def is_english_candidate(value: str) -> bool:
    """Return whether visible text is English-dominant and worth classifying."""
    text = normalize_runtime_text(value)
    if not text or CJK_PATTERN.search(text) or IDENTIFIER_PATTERN.match(text):
        return False
    words = LATIN_WORD_PATTERN.findall(text)
    return sum(len(word) for word in words) >= 3


def _json_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _json_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _json_strings(item)


def load_allowed_content(
    json_paths: Iterable[str | Path],
    explicit_text: Iterable[str],
) -> set[str]:
    """Load known user, KM, and product content that is not UI localization."""
    values = set(BUILTIN_ALLOWED_TEXT)
    values.update(explicit_text)
    for raw_path in json_paths:
        path = Path(raw_path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise LocaleToolError(f"Unable to read allowed-content JSON {path}: {error}") from error
        values.update(_json_strings(payload))

    allowed: set[str] = set()
    for value in values:
        normalized = normalize_runtime_text(value)
        visible = _visible_text_variant(value)
        if normalized:
            allowed.add(normalized)
        if visible:
            allowed.add(visible)
    return allowed


def _source_index(locale_root: Path) -> dict[str, list[dict[str, Any]]]:
    template = load_catalog(locale_root / "upstream" / "wizard.pot")
    effective = merge_catalogs(
        locale_root / "upstream" / "wizard.po",
        locale_root / "overrides" / "wizard.po",
        locale_root / "extras" / "wizard.po",
    )
    extras = load_catalog(locale_root / "extras" / "wizard.po", required=False)
    effective_index = catalog_index(effective)
    sources: dict[str, list[dict[str, Any]]] = {}

    for key, entry in catalog_index(template).items():
        status = (
            "official_translated"
            if entry_is_translated(effective_index.get(key))
            else "official_missing"
        )
        for source in source_strings(entry):
            for candidate in {normalize_runtime_text(source), _visible_text_variant(source)}:
                if not candidate:
                    continue
                sources.setdefault(candidate, []).append(
                    {
                        "status": status,
                        "msgid": entry.msgid,
                        "msgctxt": entry.msgctxt,
                    }
                )

    for entry in extras:
        if entry.obsolete:
            continue
        status = "extra_translated" if entry_is_translated(entry) else "extra_missing"
        for source in source_strings(entry):
            for candidate in {normalize_runtime_text(source), _visible_text_variant(source)}:
                if not candidate:
                    continue
                sources.setdefault(candidate, []).append(
                    {
                        "status": status,
                        "msgid": entry.msgid,
                        "msgctxt": entry.msgctxt,
                    }
                )
    return sources


def _matches_allowed_content(text: str, allowed: set[str]) -> bool:
    if text in allowed or text.strip(" .,!?…:;()[]{}·") in allowed:
        return True
    for content in allowed:
        if len(content) < 3 or content not in text:
            continue
        remainder = normalize_runtime_text(text.replace(content, " ", 1))
        if sum(len(word) for word in LATIN_WORD_PATTERN.findall(remainder)) <= 2:
            return True
    return False


def _classification(
    text: str,
    sources: Mapping[str, list[dict[str, Any]]],
    allowed: set[str],
) -> tuple[str, list[dict[str, Any]]]:
    if _matches_allowed_content(text, allowed):
        return "allowed_content", []
    matches = sources.get(text, [])
    statuses = {item["status"] for item in matches}
    if "official_missing" in statuses:
        return "official_missing", matches
    if statuses & {"official_translated", "extra_translated"}:
        return "unexpected_source", matches
    if "extra_missing" in statuses:
        return "runtime_not_in_pot", matches
    return "runtime_not_in_pot", []


def classify_runtime_observations(
    observations: Iterable[Mapping[str, str]],
    *,
    locale_root: str | Path,
    allowed_content: set[str],
) -> dict[str, Any]:
    """Classify and group English observations from all preview routes."""
    sources = _source_index(Path(locale_root).resolve())
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    candidate_locations = 0

    for observation in observations:
        text = normalize_runtime_text(observation["text"])
        if not is_english_candidate(text):
            continue
        candidate_locations += 1
        category, source_matches = _classification(text, sources, allowed_content)
        key = (category, observation["route"], text)
        finding = grouped.setdefault(
            key,
            {
                "category": category,
                "route": observation["route"],
                "url": observation["url"],
                "screenshot": f"{observation['route']}.png",
                "text": text,
                "source_matches": source_matches,
                "locations": [],
            },
        )
        location = {
            "kind": observation["kind"],
            "selector": observation["selector"],
        }
        if location not in finding["locations"]:
            finding["locations"].append(location)

    order = {
        "runtime_not_in_pot": 0,
        "official_missing": 1,
        "unexpected_source": 2,
        "allowed_content": 3,
    }
    findings = sorted(
        grouped.values(),
        key=lambda item: (order[item["category"]], item["route"], item["text"].casefold()),
    )
    counts = {category: 0 for category in order}
    for finding in findings:
        counts[finding["category"]] += 1
    return {
        "schema_version": 1,
        "candidate_locations": candidate_locations,
        "counts": counts,
        "findings": findings,
    }


def render_runtime_markdown(report: Mapping[str, Any]) -> str:
    """Render actionable runtime findings and keep allowed content in JSON only."""
    counts = report["counts"]
    lines = [
        "# Runtime UI translation scan",
        "",
        "| Category | Unique route/text pairs |",
        "| --- | ---: |",
        f"| Not in official POT | {counts['runtime_not_in_pot']} |",
        f"| Official source missing or fuzzy | {counts['official_missing']} |",
        f"| Translated source still rendered in English | {counts['unexpected_source']} |",
        f"| Known content ignored | {counts['allowed_content']} |",
        "",
    ]
    actionable = [item for item in report["findings"] if item["category"] != "allowed_content"]
    if not actionable:
        lines.append("No actionable English UI text was observed in the captured routes.")
        return "\n".join(lines) + "\n"

    labels = {
        "runtime_not_in_pot": "Not in POT",
        "official_missing": "Missing official translation",
        "unexpected_source": "English rendered despite translation",
    }
    lines.extend(
        [
            "| Category | Route | Visible text | DOM location |",
            "| --- | --- | --- | --- |",
        ]
    )
    for finding in actionable:
        selector = finding["locations"][0]["selector"].replace("|", "\\|")
        text = finding["text"].replace("|", "\\|")
        lines.append(
            f"| {labels[finding['category']]} | `{finding['route']}` | {text} | `{selector}` |"
        )
    return "\n".join(lines) + "\n"


def write_runtime_report(
    report: Mapping[str, Any], output_directory: str | Path
) -> tuple[Path, Path]:
    """Write runtime findings beside preview screenshots."""
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "runtime.json"
    markdown_path = output / "runtime.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_runtime_markdown(report), encoding="utf-8")
    return json_path, markdown_path
