"""Make confirmed hardcoded DSW frontend text localizable."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Literal

import yaml
from pydantic import Field, field_validator, model_validator

from dsw_locale_tool.config import SEMVER_PATTERN, StrictModel
from dsw_locale_tool.errors import LocaleToolError


class FrontendTransform(StrictModel):
    """One exact source change that exposes hardcoded text to gettext."""

    id: str = Field(min_length=1, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    introduced_in: str
    through: str | None = None
    path: str = Field(min_length=1)
    before: str = Field(min_length=1)
    after: str = Field(min_length=1)

    @field_validator("introduced_in", "through")
    @classmethod
    def validate_version(cls, value: str | None) -> str | None:
        """Require exact application versions for deterministic selection."""
        if value is not None and not SEMVER_PATTERN.fullmatch(value):
            raise ValueError("must be a semantic application version")
        return value

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        """Keep transforms inside the checked-out frontend repository."""
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("must be a relative repository path without '..'")
        return value

    @model_validator(mode="after")
    def validate_change(self) -> FrontendTransform:
        """Reject no-op and inverted version ranges."""
        if self.before == self.after:
            raise ValueError("before and after must differ")
        if self.through is not None and _version_key(self.through) < _version_key(
            self.introduced_in
        ):
            raise ValueError("through must not precede introduced_in")
        return self

    def applies_to(self, app_version: str) -> bool:
        """Return whether this transform belongs to an application release."""
        version = _version_key(app_version)
        return version >= _version_key(self.introduced_in) and (
            self.through is None or version <= _version_key(self.through)
        )


class FrontendManifest(StrictModel):
    """Configuration for source transforms and the published client image."""

    schema_version: Literal[1]
    upstream_repository: str = Field(min_length=1, pattern=r"^https://")
    image_repository: str = Field(min_length=1, pattern=r"^[a-z0-9./_-]+$")
    transforms: list[FrontendTransform]

    @field_validator("transforms")
    @classmethod
    def validate_unique_transforms(cls, value: list[FrontendTransform]) -> list[FrontendTransform]:
        """Keep transform identifiers stable and unambiguous."""
        identifiers = [item.id for item in value]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("transform ids must be unique")
        return value


def _version_key(version: str) -> tuple[int, int, int, bool, str]:
    match = re.fullmatch(
        r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
        r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?",
        version,
    )
    if match is None:
        raise LocaleToolError(f"Invalid application version: {version!r}")
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        match.group("prerelease") is None,
        match.group("prerelease") or "",
    )


def load_frontend_manifest(path: str | Path) -> FrontendManifest:
    """Load one strict frontend localization manifest."""
    manifest_path = Path(path)
    if not manifest_path.is_file():
        raise LocaleToolError(f"Frontend manifest does not exist: {manifest_path}")
    try:
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise LocaleToolError(f"Invalid YAML in {manifest_path}: {error}") from error
    if not isinstance(data, dict):
        raise LocaleToolError(f"Frontend manifest root must be a mapping: {manifest_path}")
    return FrontendManifest.model_validate(data)


def _selected_transforms(manifest: FrontendManifest, app_version: str) -> list[FrontendTransform]:
    _version_key(app_version)
    return [item for item in manifest.transforms if item.applies_to(app_version)]


def frontend_image_reference(
    manifest: FrontendManifest, app_version: str
) -> dict[str, str | bool | list[str]]:
    """Return the deterministic client image for one application release."""
    selected = _selected_transforms(manifest, app_version)
    if not selected:
        return {
            "app_version": app_version,
            "custom": False,
            "image": f"datastewardshipwizard/wizard-client:{app_version}",
            "transforms": [],
        }
    canonical = json.dumps(
        [item.model_dump(mode="json") for item in selected],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    tag = f"{app_version}-l10n-{digest}"
    return {
        "app_version": app_version,
        "custom": True,
        "image": f"{manifest.image_repository}:{tag}",
        "transforms": [item.id for item in selected],
    }


def localize_frontend(
    manifest: FrontendManifest,
    app_version: str,
    source_root: str | Path,
) -> dict[str, object]:
    """Apply exact transforms or verify that upstream already contains the result."""
    root = Path(source_root).resolve()
    if not root.is_dir():
        raise LocaleToolError(f"Frontend source directory does not exist: {root}")

    image = frontend_image_reference(manifest, app_version)
    results: list[dict[str, str]] = []
    for transform in _selected_transforms(manifest, app_version):
        source_path = root / transform.path
        if not source_path.is_file():
            raise LocaleToolError(
                f"Frontend transform {transform.id!r} target does not exist: {transform.path}"
            )
        contents = source_path.read_text(encoding="utf-8")
        before_count = contents.count(transform.before)
        after_count = contents.count(transform.after)
        if before_count == 1 and after_count == 0:
            source_path.write_text(
                contents.replace(transform.before, transform.after, 1),
                encoding="utf-8",
            )
            status = "applied"
        elif before_count == 0 and after_count == 1:
            status = "already-localizable"
        else:
            raise LocaleToolError(
                f"Frontend transform {transform.id!r} expected exactly one before or after "
                f"fragment in {transform.path}; found before={before_count}, after={after_count}"
            )
        results.append({"id": transform.id, "path": transform.path, "status": status})

    return {**image, "results": results}
