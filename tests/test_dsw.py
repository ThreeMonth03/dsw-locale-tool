"""DSW API and installer tests."""

from __future__ import annotations

import json
import zipfile

import pytest

from dsw_locale_tool.dsw import DswApi, read_bundle_metadata
from dsw_locale_tool.errors import LocaleToolError


class FakeResponse:
    def __init__(self, payload=None, *, status_code=200, text=""):
        self.payload = payload or {}
        self.status_code = status_code
        self.text = text

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.responses.pop(0)


def make_bundle(path):
    metadata = {
        "organizationId": "depositar",
        "localeId": "zh_Hant",
        "version": "4.32.0",
        "id": "depositar:zh_Hant:4.32.0",
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("locale/locale.json", json.dumps(metadata))
    return metadata


def test_read_bundle_metadata(tmp_path):
    bundle = tmp_path / "locale.zip"
    metadata = make_bundle(bundle)

    assert read_bundle_metadata(bundle) == metadata


def test_health_url_removes_api_mount():
    api = DswApi("http://localhost:3000/wizard-api")

    assert api.health_url == "http://localhost:3000/"


def test_use_api_key_strips_surrounding_whitespace():
    api = DswApi("http://localhost:3000/wizard-api")

    api.use_api_key("  api-key  ")

    assert api.token == "api-key"


def test_use_api_key_rejects_empty_value():
    api = DswApi("http://localhost:3000/wizard-api")

    with pytest.raises(LocaleToolError, match="cannot be empty"):
        api.use_api_key("  ")


def test_wait_until_ready_accepts_non_server_error():
    session = FakeSession([FakeResponse(status_code=404)])
    api = DswApi("http://localhost:3000/wizard-api", session=session)

    api.wait_until_ready(wait_timeout=0.1, interval=0)

    assert session.calls[0][1] == "http://localhost:3000/"


def test_wait_until_operational_retries_housekeeping(monkeypatch):
    session = FakeSession(
        [
            FakeResponse({"type": "HousekeepingInProgressClientConfig"}),
            FakeResponse({"type": "AppConfigClientConfig"}),
        ]
    )
    api = DswApi("http://localhost:3000/wizard-api", session=session)
    monkeypatch.setattr("dsw_locale_tool.dsw.time.sleep", lambda interval: None)

    api.wait_until_operational("http://localhost:8080/wizard", wait_timeout=1, interval=0)

    assert len(session.calls) == 2
    assert session.calls[0][2]["params"]["clientUrl"] == "http://localhost:8080/wizard"


def test_install_locale_imports_and_enables_new_coordinate(tmp_path):
    bundle = tmp_path / "locale.zip"
    make_bundle(bundle)
    session = FakeSession(
        [
            FakeResponse({"_embedded": {"locales": []}}),
            FakeResponse({"uuid": "locale-uuid"}, status_code=201),
            FakeResponse({"enabled": True, "defaultLocale": True}),
        ]
    )
    api = DswApi("http://localhost:3000/wizard-api", session=session)
    api.token = "secret-token"

    result = api.install_locale(bundle, default_locale=True)

    assert result == {
        "created": True,
        "id": "depositar:zh_Hant:4.32.0",
        "uuid": "locale-uuid",
        "enabled": True,
        "defaultLocale": True,
    }
    assert [call[0] for call in session.calls] == ["GET", "POST", "PUT"]
    assert session.calls[-1][2]["json"] == {"enabled": True, "defaultLocale": True}
    assert session.calls[-1][2]["headers"]["Authorization"] == "Bearer secret-token"


def test_install_locale_is_idempotent_for_existing_coordinate(tmp_path):
    bundle = tmp_path / "locale.zip"
    make_bundle(bundle)
    session = FakeSession(
        [
            FakeResponse(
                {"_embedded": {"locales": [{"uuid": "existing-uuid", "version": "4.32.0"}]}}
            ),
            FakeResponse({"enabled": True, "defaultLocale": False}),
        ]
    )
    api = DswApi("http://localhost:3000/wizard-api", session=session)
    api.token = "secret-token"

    result = api.install_locale(bundle, default_locale=False)

    assert result["created"] is False
    assert [call[0] for call in session.calls] == ["GET", "PUT"]


def test_seed_project_imports_package_then_creates_project(tmp_path):
    knowledge_model = tmp_path / "preview.km"
    knowledge_model.write_text('{"id": "test:km:1.0.0"}', encoding="utf-8")
    session = FakeSession(
        [
            FakeResponse({"uuid": "package-uuid"}, status_code=201),
            FakeResponse({"uuid": "project-uuid"}, status_code=201),
        ]
    )
    api = DswApi("http://localhost:3000/wizard-api", session=session)
    api.token = "secret-token"

    project_uuid = api.seed_project(knowledge_model)

    assert project_uuid == "project-uuid"
    project_body = session.calls[1][2]["json"]
    assert project_body["knowledgeModelPackageUuid"] == "package-uuid"
    assert project_body["visibility"] == "PrivateProjectVisibility"
