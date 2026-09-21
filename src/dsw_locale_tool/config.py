"""Strict configuration for official DSW translation synchronization."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

from dsw_locale_tool.errors import LocaleToolError

VERSION_KEY_PATTERN = re.compile(r"^v\d+\.\d+$")


class StrictModel(BaseModel):
    """Reject misspelled and removed settings."""

    model_config = ConfigDict(extra="forbid")


class UpstreamConfig(StrictModel):
    """Official source repository and translation language."""

    repository: str
    locale: Literal["zh_Hant"] = "zh_Hant"


class WeblateConfig(StrictModel):
    """Read-only release discovery endpoints."""

    projects_url: Literal["https://localize.ds-wizard.org/api/projects/"] = (
        "https://localize.ds-wizard.org/api/projects/"
    )
    public_projects_url: Literal["https://localize.ds-wizard.org/projects/"] = (
        "https://localize.ds-wizard.org/projects/"
    )


class VersionConfig(StrictModel):
    """A DSW minor version, not a separately released local locale."""

    upstream_ref: str
    state: Literal["active", "maintenance"]


class BranchConfig(StrictModel):
    """Fixed repository layout used by the workflows."""

    control: Literal["main"] = "main"
    version_prefix: Literal["sync/"] = "sync/"


class TranslationConfig(StrictModel):
    """Translation repository configuration."""

    schema_version: Literal[2]
    upstream: UpstreamConfig
    weblate: WeblateConfig = WeblateConfig()
    branches: BranchConfig = BranchConfig()
    versions: dict[str, VersionConfig]

    @field_validator("versions")
    @classmethod
    def validate_versions(cls, value: dict[str, VersionConfig]) -> dict[str, VersionConfig]:
        if not value:
            raise ValueError("at least one DSW version must be configured")
        for key, version in value.items():
            if not VERSION_KEY_PATTERN.fullmatch(key) or version.upstream_ref != key:
                raise ValueError(f"version and upstream_ref must match v<major>.<minor>: {key!r}")
        return value

    def version(self, version_key: str) -> VersionConfig:
        try:
            return self.versions[version_key]
        except KeyError as error:
            raise LocaleToolError(f"Unknown DSW version: {version_key!r}") from error


def load_config(path: str | Path) -> TranslationConfig:
    """Read a configuration without accepting obsolete package settings."""
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise LocaleToolError(f"Unable to read configuration: {path}") from error
    if not isinstance(data, dict):
        raise LocaleToolError("Configuration root must be a mapping")
    return TranslationConfig.model_validate(data)
