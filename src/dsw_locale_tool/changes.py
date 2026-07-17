"""Validate the scope and version metadata of translation pull requests."""

from __future__ import annotations

import copy
import os
import re
from pathlib import Path
from typing import Any

import yaml

from dsw_locale_tool.config import load_config
from dsw_locale_tool.errors import LocaleToolError

RELEASE_VERSION_PATTERN = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")


def _repository_files(root: Path) -> dict[str, tuple[str, bytes]]:
    files: dict[str, tuple[str, bytes]] = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        name = relative.as_posix()
        if path.is_symlink():
            files[name] = ("symlink", os.readlink(path).encode())
        elif path.is_file():
            files[name] = ("file", path.read_bytes())
    return files


def _changed_paths(base_root: Path, head_root: Path) -> list[str]:
    base = _repository_files(base_root)
    head = _repository_files(head_root)
    return sorted(path for path in set(base) | set(head) if base.get(path) != head.get(path))


def _translation_path_allowed(path: str) -> bool:
    candidate = Path(path)
    parts = candidate.parts
    if path in {
        "README.md",
        "CONTRIBUTING.md",
        "glossary/zh-Hant.csv",
        "locale/README.md",
        "translation-config.yml",
    }:
        return True
    if len(parts) == 2 and parts[0] in {"overrides", "extras"}:
        return candidate.suffix == ".po"
    return len(parts) >= 2 and parts[0] == "docs" and candidate.suffix == ".md"


def _yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise LocaleToolError(f"Unable to read configuration for PR validation: {path}") from error
    if not isinstance(value, dict):
        raise LocaleToolError(f"Configuration root must be a mapping: {path}")
    return value


def _release_tuple(value: str) -> tuple[int, int, int]:
    match = RELEASE_VERSION_PATTERN.fullmatch(value)
    if not match:
        raise LocaleToolError(f"Locale release version must use X.Y.Z: {value!r}")
    return tuple(int(match.group(name)) for name in ("major", "minor", "patch"))


def _validate_config_change(base_path: Path, head_path: Path, version_key: str) -> bool:
    base = _yaml_mapping(base_path)
    head = _yaml_mapping(head_path)
    if base == head:
        return False

    try:
        base_version = base["versions"][version_key]["locale_version"]
        head_version = head["versions"][version_key]["locale_version"]
    except (KeyError, TypeError) as error:
        raise LocaleToolError(
            f"Both configurations must contain {version_key}.locale_version"
        ) from error

    normalized = copy.deepcopy(head)
    normalized["versions"][version_key]["locale_version"] = base_version
    if normalized != base:
        raise LocaleToolError(
            "translation-config.yml may only bump locale_version for the target release line"
        )
    if _release_tuple(head_version) <= _release_tuple(base_version):
        raise LocaleToolError(f"locale_version must increase: {base_version!r} -> {head_version!r}")
    return True


def validate_translation_pr(
    base_root: str | Path,
    head_root: str | Path,
    branch: str,
) -> dict[str, Any]:
    """Validate one PR targeting a ``sync/vX.Y`` translation branch."""
    base = Path(base_root).resolve()
    head = Path(head_root).resolve()
    base_config = load_config(base / "translation-config.yml")
    head_config = load_config(head / "translation-config.yml")
    prefix = head_config.branches.version_prefix
    if base_config.branches.version_prefix != prefix or not branch.startswith(prefix):
        raise LocaleToolError(f"Target branch must match {prefix}v<major>.<minor>: {branch!r}")
    version_key = branch.removeprefix(prefix)
    head_config.version(version_key)
    base_config.version(version_key)

    changed = _changed_paths(base, head)
    forbidden = [path for path in changed if not _translation_path_allowed(path)]
    if forbidden:
        raise LocaleToolError(
            "Translation PR changes forbidden paths: "
            + ", ".join(f"{path!r}" for path in forbidden)
        )
    symlinks = [path for path in changed if (head / path).is_symlink()]
    if symlinks:
        raise LocaleToolError(
            "Translation PR must not add symlinks: " + ", ".join(f"{path!r}" for path in symlinks)
        )

    version_bumped = _validate_config_change(
        base / "translation-config.yml",
        head / "translation-config.yml",
        version_key,
    )
    return {
        "valid": True,
        "branch": branch,
        "version": version_key,
        "changed_paths": changed,
        "locale_version_bumped": version_bumped,
    }
