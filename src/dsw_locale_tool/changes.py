"""Validate translation pull requests without executing contributor code."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import Any

from dsw_locale_tool.catalog import catalog_index, load_catalog
from dsw_locale_tool.config import load_config
from dsw_locale_tool.errors import LocaleToolError
from dsw_locale_tool.translation_tree import parse_translation_unit


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
        "translations/README.md",
    }:
        return True
    if len(parts) >= 3 and parts[0] == "translations":
        return parts[1] in {"wizard", "mail"} and path.endswith(".translation.md")
    return len(parts) >= 2 and parts[0] == "docs" and candidate.suffix == ".md"


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

    forms = [path for path in changed if path.endswith(".translation.md")]
    for path in forms:
        if not (head / path).is_file():
            raise LocaleToolError(f"Translation forms must not be removed: {path}")
        after = parse_translation_unit(head / path, head)
        if (base / path).is_file():
            before = parse_translation_unit(base / path, base)
            if replace(after, translation=before.translation) != before:
                raise LocaleToolError(f"Translation source and metadata are read-only: {path}")
        else:
            template = catalog_index(load_catalog(base / "upstream" / f"{after.component}.pot"))
            entry = template.get((after.msgctxt, after.msgid))
            if entry is None or (entry.msgid_plural or None) != after.msgid_plural:
                raise LocaleToolError(
                    f"New translation form must match an official POT entry: {path}"
                )
    return {
        "valid": True,
        "branch": branch,
        "version": version_key,
        "translation_changed": any(
            path.startswith("translations/") and path.endswith(".translation.md")
            for path in changed
        ),
        "changed_paths": changed,
    }
