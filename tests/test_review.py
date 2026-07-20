"""Public translation review policy tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import requests
from pydantic import ValidationError

from dsw_locale_tool.errors import LocaleToolError
from dsw_locale_tool.review import (
    ReviewMetadata,
    generate_review_site,
    latest_review_heartbeat,
    load_review_manifest,
    review_expiry_reason,
    review_routes,
    verify_review_gateway,
)

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "review" / "pages.yml"


def test_review_manifest_is_the_route_policy_for_public_and_authenticated_pages():
    manifest = load_review_manifest(MANIFEST)

    assert review_routes(manifest, None, authenticated=False) == {"login": "/login"}
    project_routes = review_routes(manifest, "project-uuid", authenticated=True)
    assert project_routes["dashboard"] == "/dashboard"
    assert project_routes["locales"] == "/locales"
    assert project_routes["questionnaire"] == "/projects/project-uuid"
    assert all("{" not in route for route in project_routes.values())


@pytest.mark.parametrize(
    "old, replacement, message",
    (
        (
            "route: /projects/{project_uuid}",
            "route: /projects/{unknown}",
            "project_uuid",
        ),
        (
            "route: /projects/{project_uuid}",
            "route: https://example.test",
            "absolute application path",
        ),
        (
            "route: /projects/{project_uuid}",
            'route: "/projects/{project_uuid}\\ninvalid 1;"',
            "safe application path characters",
        ),
        ("requires_project: true", "requires_project: false", "requires_project"),
    ),
)
def test_review_manifest_rejects_unsafe_or_inconsistent_routes(tmp_path, old, replacement, message):
    source = MANIFEST.read_text(encoding="utf-8")
    source = source.replace(old, replacement, 1)
    candidate = tmp_path / "pages.yml"
    candidate.write_text(source, encoding="utf-8")

    with pytest.raises(ValidationError, match=message):
        load_review_manifest(candidate)


def test_review_manifest_rejects_multiline_browser_selectors(tmp_path):
    source = MANIFEST.read_text(encoding="utf-8").replace(
        "trigger: .row.mt-4.mb-1 a.fw-bold",
        'trigger: ".row\\nbutton"',
        1,
    )
    candidate = tmp_path / "pages.yml"
    candidate.write_text(source, encoding="utf-8")

    with pytest.raises(ValidationError, match="single-line CSS selector"):
        load_review_manifest(candidate)


def test_generate_review_site_writes_portal_config_and_exact_nginx_map(tmp_path):
    metadata = ReviewMetadata(
        dsw_version="4.32.1",
        translation_ref="sync/v4.32",
        revision="abcdef1234567890",
        pull_request_url="https://github.com/example/locale/pull/7",
        idle_timeout_minutes=30,
        hard_timeout_minutes=180,
    )
    payload = generate_review_site(
        load_review_manifest(MANIFEST),
        tmp_path / "site",
        project_uuid="project-uuid",
        reviewer_email="reviewer@example.test",
        reviewer_password="disposable",
        metadata=metadata,
    )

    site = tmp_path / "site"
    assert (site / "index.html").is_file()
    assert (site / "review" / "portal.js").is_file()
    assert payload["reviewer"] == {
        "email": "reviewer@example.test",
        "password": "disposable",
    }
    assert payload["metadata"]["dswVersion"] == "4.32.1"
    assert payload["metadata"]["translationRef"] == "sync/v4.32"
    assert payload["metadata"]["revision"] == "abcdef1234567890"
    assert payload["metadata"]["idleTimeoutMinutes"] == 30
    assert payload["metadata"]["hardTimeoutMinutes"] == 180
    assert (
        next(page for page in payload["pages"] if page["name"] == "dashboard")["path"]
        == "/wizard/dashboard"
    )
    assert "/wizard/" in payload["allowedPaths"]
    assert "/wizard/dashboard" in payload["allowedPaths"]
    assert "/wizard/projects/project-uuid" in payload["allowedPaths"]
    assert "/wizard/users" not in payload["allowedPaths"]
    route_map = (site / "allowed-routes.map").read_text(encoding="utf-8").splitlines()
    assert "/wizard/projects/project-uuid 1;" in route_map
    assert route_map == sorted(route_map)
    assert json.loads((site / "review" / "review.json").read_text(encoding="utf-8")) == payload
    assert (site / "review" / "heartbeat.js").is_file()


def test_review_metadata_has_an_absolute_hard_expiry():
    metadata = ReviewMetadata(
        dsw_version="4.32.1",
        translation_ref="sync/v4.32",
        revision="abcdef12",
        idle_timeout_minutes=30,
        hard_timeout_minutes=180,
    )

    payload = metadata.public_payload(datetime(2026, 7, 20, 8, 0, tzinfo=UTC))

    assert payload["generatedAt"] == "2026-07-20T08:00:00Z"
    assert payload["hardExpiresAt"] == "2026-07-20T11:00:00Z"


def test_review_metadata_rejects_invalid_lifetime_and_pull_request_url():
    with pytest.raises(ValidationError, match="hard timeout"):
        ReviewMetadata(
            dsw_version="4.32.1",
            translation_ref="sync/v4.32",
            revision="abcdef12",
            idle_timeout_minutes=30,
            hard_timeout_minutes=20,
        )
    with pytest.raises(ValidationError, match="public HTTPS URL"):
        ReviewMetadata(
            dsw_version="4.32.1",
            translation_ref="sync/v4.32",
            revision="abcdef12",
            pull_request_url="http://localhost/pull/7",
            idle_timeout_minutes=30,
            hard_timeout_minutes=180,
        )


def test_review_heartbeat_parser_and_expiry_policy():
    logs = (
        "gateway | unrelated\ngateway | DSW_REVIEW_HEARTBEAT 100.25\nDSW_REVIEW_HEARTBEAT 160.5\n"
    )

    assert latest_review_heartbeat(logs) == 160.5
    assert latest_review_heartbeat("unrelated") is None
    assert (
        review_expiry_reason(
            now=1900,
            started_at=0,
            last_activity_at=150,
            idle_timeout_seconds=1800,
            hard_timeout_seconds=10800,
        )
        is None
    )
    assert (
        review_expiry_reason(
            now=1950,
            started_at=0,
            last_activity_at=150,
            idle_timeout_seconds=1800,
            hard_timeout_seconds=10800,
        )
        == "idle"
    )
    assert (
        review_expiry_reason(
            now=10800,
            started_at=0,
            last_activity_at=10799,
            idle_timeout_seconds=1800,
            hard_timeout_seconds=10800,
        )
        == "hard-limit"
    )


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None):
        self.status_code = status_code
        self.ok = 200 <= status_code < 400
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.requests: list[tuple[str, str, dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs: Any):
        self.requests.append((method, url, kwargs))
        path = url.removeprefix("https://review.example.test")
        if method == "POST" and path == "/wizard-api/tokens":
            return FakeResponse(200, {"token": "review-token"})
        if method == "POST" and path == "/review/heartbeat":
            return FakeResponse(204)
        if method == "GET" and path == "/wizard-api/users/current":
            return FakeResponse(200, {"uuid": "reviewer"})
        if path in {"/", "/wizard/login"}:
            return FakeResponse(200)
        if path == "/wizard/users":
            return FakeResponse(404)
        return FakeResponse(403)


def test_gateway_verifier_checks_login_reads_writes_websockets_and_page_policy():
    session = FakeSession()

    result = verify_review_gateway(
        "https://review.example.test/",
        email="reviewer@example.test",
        password="disposable",
        session=session,
    )

    assert result == {
        "portal": 200,
        "heartbeat": 204,
        "login-page": 200,
        "login": 200,
        "read-api": 200,
        "update-tour": 403,
        "create-project": 403,
        "delete-token": 403,
        "websocket": 403,
        "disallowed-page": 404,
    }
    write_requests = [method for method, _, _ in session.requests if method in {"PUT", "DELETE"}]
    assert write_requests == ["PUT", "DELETE"]


def test_gateway_verifier_fails_closed_when_a_write_is_allowed():
    class UnsafeSession(FakeSession):
        def request(self, method: str, url: str, **kwargs: Any):
            response = super().request(method, url, **kwargs)
            if method == "POST" and url.endswith("/wizard-api/projects"):
                return FakeResponse(422)
            return response

    with pytest.raises(LocaleToolError, match="allowed create-project"):
        verify_review_gateway(
            "https://review.example.test",
            email="reviewer@example.test",
            password="disposable",
            session=UnsafeSession(),
        )


def test_gateway_verifier_waits_for_gateway_readiness(monkeypatch):
    class StartingSession(FakeSession):
        attempts = 0

        def request(self, method: str, url: str, **kwargs: Any):
            if method == "GET" and url == "https://review.example.test/":
                self.attempts += 1
                if self.attempts == 1:
                    raise requests.ConnectionError("starting")
            return super().request(method, url, **kwargs)

    monkeypatch.setattr("dsw_locale_tool.review.time.sleep", lambda _: None)
    session = StartingSession()

    verify_review_gateway(
        "https://review.example.test",
        email="reviewer@example.test",
        password="disposable",
        session=session,
    )

    assert session.attempts == 2
