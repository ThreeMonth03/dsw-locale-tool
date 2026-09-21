"""Synchronize a version branch with the official DSW locale repository."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

from dsw_locale_tool.config import TranslationConfig
from dsw_locale_tool.errors import LocaleToolError

MANAGED_FILES = (
    ("wizard.pot", "wizard.pot"),
    ("mail.pot", "mail.pot"),
    ("wizard.po", "wizard.po"),
    ("mail.po", "mail.po"),
)
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
UPSTREAM_BRANCH_PATTERN = re.compile(r"^refs/heads/(?P<version>v\d+\.\d+)$")


def _run(command: list[str], *, cwd: Path | None = None) -> str:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise LocaleToolError(f"Required command is unavailable: {command[0]}") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or error.stdout.strip() or str(error)
        raise LocaleToolError(f"Command failed: {' '.join(command)}\n{detail}") from error
    return result.stdout.strip()


def sync_upstream(
    config: TranslationConfig,
    version_key: str,
    output_root: str | Path,
) -> dict[str, object]:
    """Copy the managed baseline files for one DSW release into ``upstream/``."""
    version = config.version(version_key)
    output = Path(output_root).resolve()
    upstream_output = output / "upstream"
    upstream_output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="dsw-locale-sync-") as temporary_directory:
        checkout = Path(temporary_directory) / "wizard-locales"
        _run(
            [
                "git",
                "clone",
                "--quiet",
                "--depth",
                "1",
                "--branch",
                version.upstream_ref,
                config.upstream.repository,
                str(checkout),
            ]
        )
        commit = _run(["git", "rev-parse", "HEAD"], cwd=checkout)
        locale_root = checkout / "locales" / config.upstream.locale

        for source_name, destination_name in MANAGED_FILES:
            source = (
                checkout / source_name
                if source_name.endswith(".pot")
                else locale_root / source_name
            )
            if not source.is_file():
                raise LocaleToolError(f"Upstream file does not exist: {source}")
            shutil.copy2(source, upstream_output / destination_name)

    lock = {
        "schema_version": 1,
        "repository": config.upstream.repository,
        "ref": version.upstream_ref,
        "commit": commit,
        "locale": config.upstream.locale,
        "version": version_key,
    }
    lock_path = upstream_output / "upstream.lock.yml"
    lock_path.write_text(
        yaml.safe_dump(lock, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return lock


def fetch_upstream_branch_heads(repository: str) -> dict[str, str]:
    """Return DSW minor release branches and their current commit SHAs."""
    output = _run(
        [
            "git",
            "ls-remote",
            "--heads",
            repository,
            "refs/heads/v*",
        ]
    )
    branches: dict[str, str] = {}
    for line in output.splitlines():
        try:
            commit, ref = line.split(maxsplit=1)
        except ValueError as error:
            raise LocaleToolError(f"Unexpected git ls-remote output: {line!r}") from error
        match = UPSTREAM_BRANCH_PATTERN.fullmatch(ref)
        if match is None:
            continue
        if not COMMIT_PATTERN.fullmatch(commit):
            raise LocaleToolError(f"Upstream branch {ref!r} has an invalid commit SHA")
        branches[match.group("version")] = commit
    return branches


def validate_upstream_lock(
    config: TranslationConfig,
    version_key: str,
    repository_root: str | Path,
) -> dict[str, object]:
    """Verify that a build uses a committed baseline for the requested release line."""
    version = config.version(version_key)
    lock_path = Path(repository_root).resolve() / "upstream" / "upstream.lock.yml"
    if not lock_path.is_file():
        raise LocaleToolError(f"Committed upstream lock does not exist: {lock_path}")
    try:
        lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise LocaleToolError(f"Invalid upstream lock {lock_path}: {error}") from error
    if not isinstance(lock, dict):
        raise LocaleToolError(f"Upstream lock must be a mapping: {lock_path}")

    expected = {
        "schema_version": 1,
        "repository": config.upstream.repository,
        "ref": version.upstream_ref,
        "locale": config.upstream.locale,
        "version": version_key,
    }
    for key, expected_value in expected.items():
        if lock.get(key) != expected_value:
            raise LocaleToolError(
                f"Upstream lock {key!r} is {lock.get(key)!r}; expected {expected_value!r}"
            )
    commit = lock.get("commit")
    if not isinstance(commit, str) or not COMMIT_PATTERN.fullmatch(commit):
        raise LocaleToolError("Upstream lock commit must be a full 40-character Git SHA")
    return lock
