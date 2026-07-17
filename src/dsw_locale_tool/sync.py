"""Synchronize a version branch with the official DSW locale repository."""

from __future__ import annotations

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
    ("locale.json", "locale.json"),
    ("README.md", "README.md"),
)


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
