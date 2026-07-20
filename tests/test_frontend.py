"""Frontend localization transform tests."""

from __future__ import annotations

import pytest

from dsw_locale_tool.errors import LocaleToolError
from dsw_locale_tool.frontend import (
    FrontendManifest,
    frontend_image_reference,
    localize_frontend,
)

TARGET = "app-wizard/elm/Wizard/Pages/Settings/OpenIdCreate/View.elm"
BEFORE = 'strong [] [ text "Scopes" ]'
AFTER = 'strong [] [ text (gettext "Scopes" appState.locale) ]'


def make_manifest(**transform_updates) -> FrontendManifest:
    """Build one strict manifest fixture."""
    transform = {
        "id": "openid-scopes-gettext",
        "introduced_in": "4.31.0",
        "path": TARGET,
        "before": BEFORE,
        "after": AFTER,
        **transform_updates,
    }
    return FrontendManifest.model_validate(
        {
            "schema_version": 1,
            "upstream_repository": "https://github.com/ds-wizard/engine-frontend.git",
            "image_repository": "ghcr.io/example/dsw-wizard-client",
            "transforms": [transform],
        }
    )


def test_frontend_reference_uses_official_image_before_transform_range():
    result = frontend_image_reference(make_manifest(), "4.30.0")

    assert result == {
        "app_version": "4.30.0",
        "custom": False,
        "image": "datastewardshipwizard/wizard-client:4.30.0",
        "transforms": [],
    }


def test_frontend_reference_treats_prerelease_as_earlier_than_stable_release():
    result = frontend_image_reference(make_manifest(), "4.31.0-rc.1")

    assert result["custom"] is False


def test_frontend_reference_is_immutable_and_version_specific():
    first = frontend_image_reference(make_manifest(), "4.31.0")
    repeated = frontend_image_reference(make_manifest(), "4.31.0")
    next_release = frontend_image_reference(make_manifest(), "4.32.0")

    assert first == repeated
    assert first["custom"] is True
    assert first["image"].startswith("ghcr.io/example/dsw-wizard-client:4.31.0-l10n-")
    assert first["image"] != next_release["image"]
    assert first["transforms"] == ["openid-scopes-gettext"]


def test_localize_frontend_applies_exact_change_and_is_idempotent(tmp_path):
    target = tmp_path / TARGET
    target.parent.mkdir(parents=True)
    target.write_text(f"before\n{BEFORE}\nafter\n", encoding="utf-8")

    applied = localize_frontend(make_manifest(), "4.31.0", tmp_path)
    repeated = localize_frontend(make_manifest(), "4.31.0", tmp_path)

    assert applied["results"][0]["status"] == "applied"
    assert repeated["results"][0]["status"] == "already-localizable"
    assert target.read_text(encoding="utf-8") == f"before\n{AFTER}\nafter\n"


def test_localize_frontend_rejects_changed_upstream_source(tmp_path):
    target = tmp_path / TARGET
    target.parent.mkdir(parents=True)
    target.write_text('strong [] [ text "Permissions" ]\n', encoding="utf-8")

    with pytest.raises(LocaleToolError, match="found before=0, after=0"):
        localize_frontend(make_manifest(), "4.31.0", tmp_path)


def test_localize_frontend_ignores_non_applicable_transform(tmp_path):
    result = localize_frontend(make_manifest(), "4.30.0", tmp_path)

    assert result["custom"] is False
    assert result["results"] == []


def test_manifest_rejects_path_escape_and_inverted_range():
    with pytest.raises(ValueError, match="relative repository path"):
        make_manifest(path="../View.elm")
    with pytest.raises(ValueError, match="must not precede"):
        make_manifest(through="4.30.0")


def test_transform_can_end_before_a_fixed_upstream_release(tmp_path):
    manifest = make_manifest(through="4.32.9")

    assert localize_frontend(manifest, "4.33.0", tmp_path)["custom"] is False
