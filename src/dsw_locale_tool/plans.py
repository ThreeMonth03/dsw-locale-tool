"""Deterministic execution plans derived from translation configuration."""

from __future__ import annotations

from dsw_locale_tool.config import VERSION_KEY_PATTERN, TranslationConfig


def _version_sort_key(version_key: str) -> tuple[int, int]:
    match = VERSION_KEY_PATTERN.fullmatch(version_key)
    if match is None:  # TranslationConfig has already validated this invariant.
        raise ValueError(f"Invalid configured version: {version_key}")
    return int(match.group("major")), int(match.group("minor"))


def build_maintained_matrix(config: TranslationConfig) -> dict[str, list[dict[str, str]]]:
    """Return the GitHub Actions matrix for every maintained release line."""
    include = []
    for version_key in sorted(config.versions, key=_version_sort_key):
        version = config.versions[version_key]
        if version.state == "retired":
            continue
        include.append(
            {
                "config_version": version_key,
                "translation_ref": f"{config.branches.version_prefix}{version_key}",
                "dsw_image_tag": version_key.removeprefix("v"),
            }
        )
    return {"include": include}


def build_release_info(config: TranslationConfig, version_key: str) -> dict[str, str]:
    """Return immutable release coordinates for one configured release line."""
    version = config.version(version_key)
    return {
        "config_version": version_key,
        "translation_ref": f"{config.branches.version_prefix}{version_key}",
        "locale_version": version.locale_version,
        "recommended_app_version": version.recommended_app_version,
        "state": version.state,
    }
