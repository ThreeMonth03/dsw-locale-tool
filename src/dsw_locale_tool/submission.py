"""Prepare narrow translation batches and verify controlled Weblate writes."""

from __future__ import annotations

import copy
import hashlib
import json
import time
from pathlib import Path

import polib

from dsw_locale_tool.audit import audit_repository, failing_categories
from dsw_locale_tool.catalog import translated_strings
from dsw_locale_tool.errors import LocaleToolError
from dsw_locale_tool.translation_tree import COMPONENTS, load_translation_tree, unit_relative_path
from dsw_locale_tool.weblate import WeblateClient, api_identity


def identity(entry):
    return entry.msgctxt, entry.msgid, entry.msgid_plural or None


def values(entry):
    return translated_strings(entry), sorted(entry.flags)


def prepare_submission(
    root: Path, client: WeblateClient, *, limit: int = 20, allow_corrections: bool = False
) -> tuple[dict, dict]:
    """Match exact official sources; nonempty targets require an explicit correction run."""
    if not 1 <= limit <= 200:
        raise LocaleToolError("Batch limit must be between 1 and 200")
    audit = audit_repository(root)
    if failing_categories(audit, {"structure", "placeholders"}):
        raise LocaleToolError("Fix local translation checks before preparing an upload")
    catalogs = {component: client.catalog(component) for component in COMPONENTS}
    indexes = {
        component: {identity(e): e for e in po if not e.obsolete}
        for component, po in catalogs.items()
    }
    report = {
        "project": client.project,
        "language": "zh_Hant",
        "apply": False,
        "candidates": [],
        "skipped": [],
        "results": [],
        "outside_changes": [],
    }
    for unit in sorted(
        load_translation_tree(root).values(), key=lambda u: unit_relative_path(u).as_posix()
    ):
        if not unit.translation:
            continue
        key = (unit.msgctxt, unit.msgid, unit.msgid_plural)
        entry = indexes[unit.component].get(key)
        row = {
            "component": unit.component,
            "source": unit.msgid,
            "context": unit.msgctxt,
            "plural": unit.msgid_plural,
            "translation": unit.translation,
            "path": unit_relative_path(unit).as_posix(),
        }
        reason = None
        if entry is None:
            reason = "source absent from live Weblate"
        elif translated_strings(entry) == [unit.translation]:
            reason = "already matches; review state preserved"
        elif any(translated_strings(entry)) and not allow_corrections:
            reason = "nonempty official translation protected"
        elif len(report["candidates"]) >= limit:
            reason = "batch limit"
        if reason:
            report["skipped"].append({**row, "reason": reason})
        else:
            report["candidates"].append(
                {**row, "before": translated_strings(entry), "before_flags": sorted(entry.flags)}
            )
    report["plan_sha256"] = hashlib.sha256(
        json.dumps(
            {key: report[key] for key in ("project", "language", "candidates")},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return report, catalogs


def write_submission(report: dict, catalogs: dict, output: Path) -> None:
    """Store reports, preflight backups, and delta-only fuzzy PO files."""
    output.mkdir(parents=True, exist_ok=True)
    (output / "submission.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Weblate submission",
        "",
        f"Project: {report['project']}",
        f"Apply: {report['apply']}",
        f"Reviewed plan: `{report['plan_sha256']}`",
        f"Candidates: {len(report['candidates'])}",
        f"Skipped: {len(report['skipped'])}",
        "",
        "See submission.json for exact sources, prior values, and verification results.",
        "",
    ]
    if report.get("error"):
        lines.extend(["Error: " + report["error"], ""])
    for result in report["results"]:
        lines.append(f"- {result['status']}: {result['source']}")
    (output / "submission.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for component, catalog in catalogs.items():
        catalog.save(output / f"before-{component}.po")
        delta = polib.POFile()
        delta.metadata = copy.deepcopy(catalog.metadata)
        index = {identity(e): e for e in catalog if not e.obsolete}
        for row in report["candidates"]:
            if row["component"] != component:
                continue
            entry = copy.deepcopy(index[(row["context"], row["source"], row["plural"])])
            entry.msgstr = "" if row["plural"] else row["translation"]
            entry.msgstr_plural = {0: row["translation"]} if row["plural"] else {}
            entry.flags = sorted(set(entry.flags) | {"fuzzy"})
            delta.append(entry)
        if delta:
            delta.save(output / f"{component}.po")


def apply_submission(
    report: dict, catalogs: dict, client: WeblateClient, output: Path, *, settle_seconds: float = 30
) -> None:
    """Stop on conflicts or failed verification; never roll back other people's work."""
    if not client.token:
        raise LocaleToolError("Set the LOCALIZE_API_TOKEN Actions secret before applying")
    report["apply"] = True
    attempted = []
    try:
        indexes = {}
        for component in {row["component"] for row in report["candidates"]}:
            index = {}
            for unit in client.units(component):
                key = api_identity(unit)
                if key in index:
                    raise LocaleToolError("Duplicate live Weblate source identity")
                index[key] = unit
            indexes[component] = index
        for row in report["candidates"]:
            component = row["component"]
            key = row["context"], row["source"], row["plural"]
            unit = indexes[component].get(key)
            if unit is None:
                raise LocaleToolError(f"Live API source is missing: {row['path']}")
            current = client.get_unit(unit["id"], component)
            if (
                api_identity(current) != key
                or current["target"] != row["before"]
                or current.get("state") not in (0, 10, 20, 30)
                or current.get("pending")
                or ("fuzzy" in row["before_flags"]) != (current.get("state") == 10)
                or current.get("last_updated") != unit.get("last_updated")
            ):
                raise LocaleToolError(f"Weblate changed since preflight: {row['path']}")
            attempted.append((row, unit["id"]))
            client.set_fuzzy(unit["id"], row["translation"])
            saved = client.get_unit(unit["id"], component)
            if (
                api_identity(saved) != key
                or saved["target"] != [row["translation"]]
                or saved.get("state") != 10
            ):
                raise LocaleToolError(
                    f"Weblate did not retain the fuzzy translation: {row['path']}"
                )
            report["results"].append(
                {"source": row["source"], "id": unit["id"], "status": "saved fuzzy"}
            )
            write_submission(report, catalogs, output)
        if attempted and settle_seconds:
            time.sleep(settle_seconds)
        for row, unit_id in attempted:
            saved = client.get_unit(unit_id, row["component"])
            if saved["target"] != [row["translation"]] or saved.get("state") != 10:
                raise LocaleToolError(f"Weblate changed the saved translation: {row['path']}")
        for component, before in catalogs.items():
            after = client.catalog(component)
            after.save(output / f"after-{component}.po")
            allowed = {
                (row["context"], row["source"], row["plural"]): row
                for row, _ in attempted
                if row["component"] == component
            }
            old = {identity(e): e for e in before if not e.obsolete}
            new = {identity(e): e for e in after if not e.obsolete}
            for key in old.keys() | new.keys():
                if key in allowed:
                    expected = allowed[key]["translation"]
                    if (
                        key not in new
                        or translated_strings(new[key]) != [expected]
                        or "fuzzy" not in new[key].flags
                    ):
                        raise LocaleToolError("Downloaded PO does not match the saved fuzzy batch")
                elif key not in old or key not in new or values(old[key]) != values(new[key]):
                    report["outside_changes"].append({"component": component, "identity": key})
            if report["outside_changes"]:
                raise LocaleToolError(
                    "Out-of-scope changes observed; inspect report, no rollback performed"
                )
        report["verified"] = True
    except LocaleToolError as error:
        report["error"] = str(error)
        raise
    finally:
        report["attempted_ids"] = [unit_id for _, unit_id in attempted]
        write_submission(report, catalogs, output)
