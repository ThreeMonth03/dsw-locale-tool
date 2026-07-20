"""Ephemeral preview configuration tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from dsw_locale_tool.errors import LocaleToolError
from dsw_locale_tool.preview import (
    _user_content,
    _validated_file_preview,
    _wait_for_application,
    _wait_for_page_available,
    generate_preview_config,
)
from dsw_locale_tool.review import load_review_manifest, review_routes, review_scenarios

REVIEW_MANIFEST = Path(__file__).parents[1] / "review" / "pages.yml"


class FakeLocator:
    def __init__(self, visible: bool, *, settles: bool = False):
        self.visible = visible
        self.settles = settles

    @property
    def first(self):
        return self

    def is_visible(self):
        return self.visible

    def wait_for(self, *, state: str, timeout: int):
        assert timeout == 30_000
        if state == "visible" and self.visible:
            return
        if state == "hidden" and not self.visible:
            return
        if state == "hidden" and self.settles:
            self.visible = False
            return
        raise TimeoutError


class FakePage:
    url = "http://localhost:8080/wizard/locales"

    def __init__(self, visible_marker: str | None = None, *, settles: bool = False):
        self.visible_marker = visible_marker
        self.settles = settles
        self.locators: dict[str, FakeLocator] = {}

    def locator(self, selector: str):
        if selector not in self.locators:
            visible = selector == "body > :not(script)" or (
                self.visible_marker is not None and self.visible_marker in selector
            )
            self.locators[selector] = FakeLocator(
                visible,
                settles=self.settles and self.visible_marker is not None,
            )
        return self.locators[selector]


def test_generate_preview_config_creates_fresh_secret_and_rsa_key(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "dsw_locale_tool.preview.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout="-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----\n"
        ),
    )
    output = tmp_path / "runtime" / "application.yml"

    generate_preview_config(output, client_url="http://localhost:8080/wizard")

    config = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert config["general"]["clientUrl"] == "http://localhost:8080/wizard"
    assert len(config["general"]["secret"]) == 32
    assert config["general"]["rsaPrivateKey"].startswith("-----BEGIN RSA PRIVATE KEY-----")
    assert config["database"]["connectionString"].endswith("/engine-wizard")
    assert config["cloud"]["publicRegistrationEnabled"] is False


def test_wait_for_application_requires_a_mounted_visible_page():
    _wait_for_application(FakePage())


def test_wait_for_page_available_accepts_normal_page():
    _wait_for_page_available(FakePage(), "locales")


def test_wait_for_page_available_accepts_initial_router_state():
    _wait_for_page_available(FakePage("not-found", settles=True), "locales")


def test_wait_for_page_available_rejects_stable_not_found_page():
    with pytest.raises(LocaleToolError, match="route was not found"):
        _wait_for_page_available(FakePage("not-found"), "locales")


def test_user_content_includes_display_name_parts():
    assert _user_content(
        {
            "firstName": "Albert",
            "lastName": "Einstein",
            "email": "albert@example.test",
            "role": "admin",
        }
    ) == {
        "Albert",
        "Einstein",
        "Albert Einstein",
        "albert@example.test",
    }


def test_project_preview_includes_static_and_interactive_states():
    project_uuid = "project-uuid"
    manifest = load_review_manifest(REVIEW_MANIFEST)

    assert review_routes(manifest, project_uuid, authenticated=True) == {
        "dashboard": "/dashboard",
        "projects": "/projects",
        "locales": "/locales",
        "project-documents": "/project-documents",
        "settings-organization": "/settings/organization",
        "settings-authentication": "/settings/authentication",
        "settings-open-id": "/settings/open-id",
        "settings-open-id-create": "/settings/open-id/create",
        "questionnaire": "/projects/project-uuid",
        "project-settings": "/projects/project-uuid/settings",
        "questionnaire-documents": "/projects/project-uuid/documents",
    }
    scenarios = review_scenarios(manifest, project_uuid)
    assert [scenario.name for scenario in scenarios] == [
        "openid-microsoft-advanced-form",
        "openid-custom-form",
        "project-share-dialog",
        "question-comment-panel",
        "project-delete-dialog",
    ]
    assert all(scenario.ready for scenario in scenarios)
    assert scenarios[1].trigger_match == "last"
    assert scenarios[3].trigger_match == "first"


def test_preview_without_project_uses_application_routes_only():
    manifest = load_review_manifest(REVIEW_MANIFEST)

    assert review_routes(manifest, None, authenticated=True) == {
        "dashboard": "/dashboard",
        "projects": "/projects",
        "locales": "/locales",
        "project-documents": "/project-documents",
        "settings-organization": "/settings/organization",
        "settings-authentication": "/settings/authentication",
        "settings-open-id": "/settings/open-id",
        "settings-open-id-create": "/settings/open-id/create",
    }
    assert [scenario.name for scenario in review_scenarios(manifest, None)] == [
        "openid-microsoft-advanced-form",
        "openid-custom-form",
    ]


def test_file_preview_requires_a_project_and_existing_file(tmp_path):
    preview_file = tmp_path / "preview.csv"
    preview_file.write_text("header\nvalue\n", encoding="utf-8")

    assert _validated_file_preview("project-uuid", preview_file) == preview_file
    with pytest.raises(LocaleToolError, match="requires both"):
        _validated_file_preview("project-uuid", None)
    with pytest.raises(LocaleToolError, match="requires both"):
        _validated_file_preview(None, preview_file)
    with pytest.raises(LocaleToolError, match="does not exist"):
        _validated_file_preview("project-uuid", Path("missing.csv"))
