"""Build locale source directories and invoke the official DSW packager."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from dsw_locale_tool.catalog import merge_catalogs
from dsw_locale_tool.config import TranslationConfig
from dsw_locale_tool.errors import LocaleToolError
from dsw_locale_tool.sync import validate_upstream_lock

COMPONENTS = ("wizard", "mail")
PACKAGER = "@ds-wizard/locale-packager@0.3.0"


def build_source(
    config: TranslationConfig,
    version_key: str,
    root: str | Path,
    output: str | Path,
    *,
    force: bool = False,
) -> Path:
    """Build the four-file source directory consumed by DSW's locale packager."""
    version = config.version(version_key)
    repository_root = Path(root).resolve()
    output_path = Path(output).resolve()
    validate_upstream_lock(config, version_key, repository_root)

    if output_path.exists() and not output_path.is_dir():
        raise LocaleToolError(f"Output path exists and is not a directory: {output_path}")
    if output_path.exists() and any(output_path.iterdir()):
        if not force:
            raise LocaleToolError(f"Output directory is not empty: {output_path}; use --force")
        shutil.rmtree(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    for component in COMPONENTS:
        catalog = merge_catalogs(
            repository_root / "upstream" / f"{component}.po",
            repository_root / "overrides" / f"{component}.po",
            repository_root / "extras" / f"{component}.po",
        )
        catalog.save(output_path / f"{component}.po")

    metadata = {
        "organizationId": config.locale.organization_id,
        "localeId": config.locale.locale_id,
        "version": version.locale_version,
        "code": config.locale.code,
        "recommendedAppVersion": version.recommended_app_version,
        "name": config.locale.name,
        "description": config.locale.description,
        "license": config.locale.license,
    }
    (output_path / "locale.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    readme_path = repository_root / "locale" / "README.md"
    if readme_path.is_file():
        shutil.copy2(readme_path, output_path / "README.md")
    else:
        (output_path / "README.md").write_text(
            f"# {config.locale.name}\n\n{config.locale.description}\n",
            encoding="utf-8",
        )
    return output_path


def package_source(source: str | Path, output: str | Path) -> Path:
    """Create a ZIP package with the pinned official DSW locale packager."""
    source_path = Path(source).resolve()
    output_path = Path(output).resolve()
    if not source_path.is_dir():
        raise LocaleToolError(f"Locale source directory does not exist: {source_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = ["npx", "--yes", PACKAGER, str(source_path), "-o", str(output_path), "-z"]
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as error:
        raise LocaleToolError("npx is required to run the DSW locale packager") from error
    except subprocess.CalledProcessError as error:
        raise LocaleToolError(
            f"DSW locale packager failed with exit code {error.returncode}"
        ) from error
    return output_path
