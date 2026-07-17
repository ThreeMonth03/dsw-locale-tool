"""Reconcile the maintained DSW release catalog without retiring old versions."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import yaml

from dsw_locale_tool.config import TranslationConfig, load_config
from dsw_locale_tool.errors import LocaleToolError
from dsw_locale_tool.versions import WeblateVersion, version_sort_key


def _read_mapping(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise LocaleToolError(f"Unable to read version configuration: {path}") from error
    if not isinstance(value, dict) or not isinstance(value.get("versions"), dict):
        raise LocaleToolError("Version configuration must contain a versions mapping")
    return value


def reconcile_version_config(
    config_path: str | Path,
    official_versions: Iterable[WeblateVersion],
    upstream_branch_heads: Mapping[str, str],
) -> dict[str, Any]:
    """Add ready Weblate versions and update lock states in one trusted config."""
    path = Path(config_path)
    current = load_config(path)
    original = _read_mapping(path)
    updated = copy.deepcopy(original)
    versions = updated["versions"]
    official = {item.version: item for item in official_versions}
    added_versions: list[dict[str, str]] = []
    pending_versions: list[dict[str, str]] = []
    state_updates: list[dict[str, str]] = []

    for version_key in sorted(official, key=version_sort_key):
        item = official[version_key]
        if version_key in current.versions:
            configured_state = current.versions[version_key].state
            if configured_state != item.expected_state:
                versions[version_key]["state"] = item.expected_state
                state_updates.append(
                    {
                        "version": version_key,
                        "previous": configured_state,
                        "current": item.expected_state,
                    }
                )
            continue

        upstream_ref = version_key
        commit = upstream_branch_heads.get(upstream_ref)
        if commit is None:
            pending_versions.append(
                {
                    "version": version_key,
                    "upstream_ref": upstream_ref,
                    "reason": "upstream branch is not available",
                }
            )
            continue

        number = version_key.removeprefix("v")
        release = f"{number}.0"
        versions[version_key] = {
            "upstream_ref": upstream_ref,
            "locale_version": release,
            "recommended_app_version": release,
            "state": item.expected_state,
        }
        added_versions.append(
            {
                "version": version_key,
                "upstream_ref": upstream_ref,
                "upstream_commit": commit,
                "state": item.expected_state,
            }
        )

    candidate = TranslationConfig.model_validate(updated)
    changed = updated != original
    if changed:
        path.write_text(
            yaml.safe_dump(updated, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    official_keys = set(official)
    preserved_versions = sorted(
        set(candidate.versions) - official_keys,
        key=version_sort_key,
    )
    managed_versions = sorted(
        (key for key, version in candidate.versions.items() if version.state != "retired"),
        key=version_sort_key,
    )
    return {
        "schema_version": 1,
        "changed": changed,
        "added_versions": added_versions,
        "state_updates": state_updates,
        "pending_versions": pending_versions,
        "preserved_versions": preserved_versions,
        "managed_versions": managed_versions,
    }


def render_reconcile_report(report: Mapping[str, Any]) -> str:
    """Render the reconciliation result for a GitHub Actions summary."""
    lines = [
        "# DSW locale maintenance plan",
        "",
        f"Configuration changed: **{'yes' if report['changed'] else 'no'}**",
        "",
    ]
    if report["added_versions"]:
        lines.append("## Added release lines")
        lines.append("")
        for item in report["added_versions"]:
            lines.append(
                f"- `{item['version']}` from `{item['upstream_ref']}` "
                f"at `{item['upstream_commit']}` ({item['state']})"
            )
        lines.append("")
    if report["state_updates"]:
        lines.append("## Lifecycle updates")
        lines.append("")
        for item in report["state_updates"]:
            lines.append(f"- `{item['version']}`: `{item['previous']}` → `{item['current']}`")
        lines.append("")
    if report["pending_versions"]:
        lines.append("## Waiting for upstream")
        lines.append("")
        for item in report["pending_versions"]:
            lines.append(f"- `{item['version']}`: {item['reason']} (`{item['upstream_ref']}`)")
        lines.append("")
    if report["preserved_versions"]:
        lines.append(
            "Versions absent from Weblate were preserved: "
            + ", ".join(f"`{item}`" for item in report["preserved_versions"])
        )
        lines.append("")
    lines.append(
        "Managed branches: " + ", ".join(f"`sync/{item}`" for item in report["managed_versions"])
    )
    return "\n".join(lines) + "\n"


def write_reconcile_report(
    report: Mapping[str, Any], output_directory: str | Path
) -> tuple[Path, Path]:
    """Write JSON and Markdown maintenance plans."""
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "maintenance.json"
    markdown_path = output / "maintenance.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_reconcile_report(report), encoding="utf-8")
    return json_path, markdown_path
