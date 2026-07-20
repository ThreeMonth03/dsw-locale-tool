"""Translation repository configuration loading and validation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dsw_locale_tool.errors import LocaleToolError

VERSION_KEY_PATTERN = re.compile(r"^v(?P<major>\d+)\.(?P<minor>\d+)$")
SEMVER_PATTERN = re.compile(
    r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)


class StrictModel(BaseModel):
    """Base model that rejects misspelled or obsolete configuration keys."""

    model_config = ConfigDict(extra="forbid")


class LocaleMetadata(StrictModel):
    """Metadata written to the generated DSW locale package."""

    organization_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    locale_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    code: str = Field(min_length=1, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    license: str = Field(min_length=1)


class UpstreamConfig(StrictModel):
    """Location and source locale in the official wizard-locales repository."""

    repository: str = Field(min_length=1)
    locale: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")


class WeblateConfig(StrictModel):
    """Official Weblate project catalog used as the supported-version source."""

    projects_url: str = Field(
        default="https://localize.ds-wizard.org/api/projects/",
        min_length=1,
        pattern=r"^https://",
    )
    public_projects_url: str = Field(
        default="https://localize.ds-wizard.org/projects/",
        min_length=1,
        pattern=r"^https://",
    )


class PreviewArtifact(StrictModel):
    """One immutable remote artifact used to seed a DSW preview."""

    url: str = Field(min_length=1, pattern=r"^https://")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PreviewContentConfig(StrictModel):
    """Translated content installed alongside a UI locale preview."""

    knowledge_model: PreviewArtifact
    document_template: PreviewArtifact
    document_format_uuid: str = Field(
        pattern=(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
            r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        )
    )


class VersionConfig(StrictModel):
    """One supported DSW minor release line."""

    upstream_ref: str = Field(min_length=1)
    locale_version: str
    recommended_app_version: str
    state: Literal["active", "maintenance", "retired"]
    preview: PreviewContentConfig | None = None

    @field_validator("locale_version", "recommended_app_version")
    @classmethod
    def validate_semver(cls, value: str) -> str:
        """Require package versions to be valid semantic versions."""
        if not SEMVER_PATTERN.fullmatch(value):
            raise ValueError("must be a semantic version such as 4.32.0 or 4.32.0-local.1")
        return value


class BranchConfig(StrictModel):
    """Branch naming policy used by the translation repository."""

    control: str = "main"
    version_prefix: str = "sync/"


class TranslationConfig(StrictModel):
    """Top-level translation repository configuration."""

    schema_version: Literal[1]
    locale: LocaleMetadata
    upstream: UpstreamConfig
    weblate: WeblateConfig = WeblateConfig()
    branches: BranchConfig = BranchConfig()
    versions: dict[str, VersionConfig]

    @field_validator("versions")
    @classmethod
    def validate_versions(cls, value: dict[str, VersionConfig]) -> dict[str, VersionConfig]:
        """Validate release-line names and ensure refs are not accidentally shared."""
        if not value:
            raise ValueError("at least one DSW version must be configured")

        refs: set[str] = set()
        for key, version in value.items():
            match = VERSION_KEY_PATTERN.fullmatch(key)
            if not match:
                raise ValueError(f"invalid version key {key!r}; expected v<major>.<minor>")
            if version.upstream_ref in refs:
                raise ValueError(f"upstream_ref {version.upstream_ref!r} is used more than once")
            refs.add(version.upstream_ref)

            expected_prefix = key.removeprefix("v") + "."
            if not version.locale_version.startswith(expected_prefix):
                raise ValueError(f"{key}.locale_version must start with {expected_prefix!r}")
            if not version.recommended_app_version.startswith(expected_prefix):
                raise ValueError(
                    f"{key}.recommended_app_version must start with {expected_prefix!r}"
                )
        return value

    @model_validator(mode="after")
    def require_live_version(self) -> TranslationConfig:
        """Prevent a configuration with no releasable version."""
        if all(version.state == "retired" for version in self.versions.values()):
            raise ValueError("at least one version must be active or in maintenance")
        return self

    def version(self, version_key: str) -> VersionConfig:
        """Return one configured version or raise a concise user-facing error."""
        try:
            return self.versions[version_key]
        except KeyError as error:
            supported = ", ".join(sorted(self.versions))
            raise LocaleToolError(
                f"Unknown version {version_key!r}; configured versions: {supported}"
            ) from error

    def preview(self, version_key: str) -> PreviewContentConfig:
        """Return configured preview content or raise a concise error."""

        preview = self.version(version_key).preview
        if preview is None:
            raise LocaleToolError(f"No preview content is configured for {version_key}")
        return preview


def load_config(path: str | Path) -> TranslationConfig:
    """Load and validate a translation repository YAML configuration."""
    config_path = Path(path)
    if not config_path.is_file():
        raise LocaleToolError(f"Configuration file does not exist: {config_path}")

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise LocaleToolError(f"Invalid YAML in {config_path}: {error}") from error

    if not isinstance(data, dict):
        raise LocaleToolError(f"Configuration root must be a mapping: {config_path}")
    return TranslationConfig.model_validate(data)
