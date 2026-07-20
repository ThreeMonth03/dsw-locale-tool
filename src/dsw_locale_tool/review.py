"""Validated page policy and runtime helpers for the public review sandbox."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

import requests
import yaml
from pydantic import Field, field_validator, model_validator

from dsw_locale_tool.config import StrictModel
from dsw_locale_tool.dsw import DswApi
from dsw_locale_tool.errors import LocaleToolError

_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_PROJECT_PLACEHOLDER = "{project_uuid}"
_HEARTBEAT_PATTERN = re.compile(r"DSW_REVIEW_HEARTBEAT (?P<timestamp>[0-9]+(?:\.[0-9]+)?)")


def _validate_route(value: str) -> str:
    parts = urlsplit(value)
    if (
        not value.startswith("/")
        or value.startswith("//")
        or parts.scheme
        or parts.netloc
        or parts.query
        or parts.fragment
    ):
        raise ValueError("must be an absolute application path without a query or fragment")
    if any(segment in {".", ".."} for segment in parts.path.split("/")):
        raise ValueError("must not contain dot path segments")
    if not re.fullmatch(r"/[A-Za-z0-9_./{}-]*", value):
        raise ValueError("may only contain safe application path characters")
    unknown_fields = re.findall(r"{[^}]+}", value)
    if any(field != _PROJECT_PLACEHOLDER for field in unknown_fields):
        raise ValueError("may only use the {project_uuid} placeholder")
    return value


class ReviewPage(StrictModel):
    """One application route exposed to reviewers."""

    name: str = Field(min_length=1)
    title: str = Field(min_length=1)
    group: str = Field(min_length=1)
    route: str
    aliases: list[str] = Field(default_factory=list)
    authenticated: bool
    requires_project: bool

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not _NAME_PATTERN.fullmatch(value):
            raise ValueError("must be a lowercase kebab-case identifier")
        return value

    @field_validator("route")
    @classmethod
    def validate_route(cls, value: str) -> str:
        return _validate_route(value)

    @field_validator("aliases")
    @classmethod
    def validate_aliases(cls, values: list[str]) -> list[str]:
        return [_validate_route(value) for value in values]

    @model_validator(mode="after")
    def validate_project_requirement(self) -> ReviewPage:
        paths = (self.route, *self.aliases)
        if any((_PROJECT_PLACEHOLDER in path) != self.requires_project for path in paths):
            raise ValueError(
                "requires_project must match use of {project_uuid} in routes and aliases"
            )
        return self


class ReviewScenario(StrictModel):
    """A local browser interaction that reveals additional translatable text."""

    name: str = Field(min_length=1)
    title: str = Field(min_length=1)
    route: str
    trigger: str = Field(min_length=1)
    ready: str = Field(min_length=1)
    trigger_match: Literal["only", "first", "last"]
    requires_project: bool

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not _NAME_PATTERN.fullmatch(value):
            raise ValueError("must be a lowercase kebab-case identifier")
        return value

    @field_validator("route")
    @classmethod
    def validate_route(cls, value: str) -> str:
        return _validate_route(value)

    @field_validator("trigger", "ready")
    @classmethod
    def validate_selector(cls, value: str) -> str:
        if "\n" in value or "\r" in value:
            raise ValueError("must be a single-line CSS selector")
        return value

    @model_validator(mode="after")
    def validate_project_requirement(self) -> ReviewScenario:
        if (_PROJECT_PLACEHOLDER in self.route) != self.requires_project:
            raise ValueError("requires_project must match use of {project_uuid} in route")
        return self


class ReviewManifest(StrictModel):
    """Single source of truth for screenshots and public review routes."""

    schema_version: Literal[1]
    pages: list[ReviewPage] = Field(min_length=1)
    scenarios: list[ReviewScenario] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_entries(self) -> ReviewManifest:
        page_paths = [path for page in self.pages for path in (page.route, *page.aliases)]
        for label, values in (
            ("page name", [page.name for page in self.pages]),
            ("page route or alias", page_paths),
            ("scenario name", [scenario.name for scenario in self.scenarios]),
        ):
            duplicates = sorted(name for name, count in Counter(values).items() if count > 1)
            if duplicates:
                raise ValueError(f"duplicate {label}: {', '.join(duplicates)}")
        page_routes = {page.route for page in self.pages}
        unknown_routes = sorted({scenario.route for scenario in self.scenarios} - page_routes)
        if unknown_routes:
            raise ValueError(
                "scenario routes must also be review pages: " + ", ".join(unknown_routes)
            )
        return self


class ResolvedReviewScenario(StrictModel):
    """Interactive scenario after substituting the disposable project UUID."""

    name: str
    title: str
    route: str
    trigger: str
    ready: str
    trigger_match: Literal["only", "first", "last"]


class ReviewMetadata(StrictModel):
    """Release and lifetime details displayed by an ephemeral review sandbox."""

    dsw_version: str = Field(min_length=1)
    translation_ref: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    pull_request_url: str | None = None
    idle_timeout_minutes: int = Field(ge=1, le=360)
    hard_timeout_minutes: int = Field(ge=1, le=360)

    @field_validator("pull_request_url")
    @classmethod
    def validate_pull_request_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parts = urlsplit(value)
        if parts.scheme != "https" or not parts.netloc or parts.username or parts.password:
            raise ValueError("must be a public HTTPS URL")
        return value

    @model_validator(mode="after")
    def validate_timeouts(self) -> ReviewMetadata:
        if self.hard_timeout_minutes < self.idle_timeout_minutes:
            raise ValueError("hard timeout must not be shorter than idle timeout")
        return self

    def public_payload(self, generated_at: datetime | None = None) -> dict[str, Any]:
        """Return browser-safe metadata with an absolute hard-expiry timestamp."""
        created = generated_at or datetime.now(UTC)
        if created.tzinfo is None:
            raise ValueError("generated_at must include a timezone")
        created = created.astimezone(UTC)
        expires = created + timedelta(minutes=self.hard_timeout_minutes)
        return {
            "dswVersion": self.dsw_version,
            "translationRef": self.translation_ref,
            "revision": self.revision,
            "pullRequestUrl": self.pull_request_url,
            "idleTimeoutMinutes": self.idle_timeout_minutes,
            "hardTimeoutMinutes": self.hard_timeout_minutes,
            "generatedAt": created.isoformat().replace("+00:00", "Z"),
            "hardExpiresAt": expires.isoformat().replace("+00:00", "Z"),
        }


def load_review_manifest(path: str | Path) -> ReviewManifest:
    """Load the strict review route manifest."""
    manifest_path = Path(path)
    if not manifest_path.is_file():
        raise LocaleToolError(f"Review manifest does not exist: {manifest_path}")
    try:
        payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise LocaleToolError(f"Invalid YAML in {manifest_path}: {error}") from error
    if not isinstance(payload, dict):
        raise LocaleToolError(f"Review manifest root must be a mapping: {manifest_path}")
    return ReviewManifest.model_validate(payload)


def _resolve_route(route: str, project_uuid: str | None) -> str:
    if _PROJECT_PLACEHOLDER not in route:
        return route
    if not project_uuid:
        raise LocaleToolError("A project UUID is required for this review route")
    if not re.fullmatch(r"[A-Za-z0-9-]+", project_uuid):
        raise LocaleToolError("Project UUID contains characters that are unsafe in a route")
    return route.replace(_PROJECT_PLACEHOLDER, project_uuid)


def review_routes(
    manifest: ReviewManifest,
    project_uuid: str | None,
    *,
    authenticated: bool | None = None,
) -> dict[str, str]:
    """Resolve available routes, optionally selecting by authentication requirement."""
    return {
        page.name: _resolve_route(page.route, project_uuid)
        for page in manifest.pages
        if (authenticated is None or page.authenticated is authenticated)
        and (project_uuid is not None or not page.requires_project)
    }


def review_allowed_routes(
    manifest: ReviewManifest,
    project_uuid: str | None,
) -> tuple[str, ...]:
    """Resolve every primary route and routing alias exposed by the review gateway."""
    return tuple(
        _resolve_route(route, project_uuid)
        for page in manifest.pages
        if project_uuid is not None or not page.requires_project
        for route in (page.route, *page.aliases)
    )


def review_scenarios(
    manifest: ReviewManifest, project_uuid: str | None
) -> tuple[ResolvedReviewScenario, ...]:
    """Resolve available interactive review scenarios."""
    return tuple(
        ResolvedReviewScenario(
            name=scenario.name,
            title=scenario.title,
            route=_resolve_route(scenario.route, project_uuid),
            trigger=scenario.trigger,
            ready=scenario.ready,
            trigger_match=scenario.trigger_match,
        )
        for scenario in manifest.scenarios
        if project_uuid is not None or not scenario.requires_project
    )


def _client_route(route: str) -> str:
    return "/wizard/" if route == "/" else f"/wizard{route}"


def generate_review_site(
    manifest: ReviewManifest,
    output: str | Path,
    *,
    project_uuid: str | None,
    reviewer_email: str,
    reviewer_password: str,
    metadata: ReviewMetadata,
) -> dict[str, Any]:
    """Create the static portal, browser guard configuration, and Nginx route map."""
    output_path = Path(output)
    if output_path.exists():
        shutil.rmtree(output_path)
    output_path.mkdir(parents=True)
    review_dir = output_path / "review"
    review_dir.mkdir()

    assets = files("dsw_locale_tool").joinpath("review_site")
    for resource in assets.iterdir():
        if resource.is_file():
            destination = output_path if resource.name == "index.html" else review_dir
            (destination / resource.name).write_bytes(resource.read_bytes())

    pages_by_name = {page.name: page for page in manifest.pages}
    routes = review_routes(manifest, project_uuid)
    public_pages = [
        {
            "name": name,
            "title": pages_by_name[name].title,
            "group": pages_by_name[name].group,
            "path": _client_route(route),
            "authenticated": pages_by_name[name].authenticated,
        }
        for name, route in routes.items()
    ]
    payload = {
        "schemaVersion": 1,
        "reviewer": {"email": reviewer_email, "password": reviewer_password},
        "metadata": metadata.public_payload(),
        "pages": public_pages,
        "allowedPaths": sorted(
            {_client_route(route) for route in review_allowed_routes(manifest, project_uuid)}
        ),
    }
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    (review_dir / "config.js").write_text(
        f"window.dswReview = Object.freeze({serialized});\n", encoding="utf-8"
    )
    (review_dir / "review.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_path / "allowed-routes.map").write_text(
        "".join(f"{path} 1;\n" for path in sorted(payload["allowedPaths"])),
        encoding="utf-8",
    )
    return payload


def prepare_review(
    *,
    api_url: str,
    client_url: str,
    email: str,
    password: str,
    locale_bundle: str | Path,
    knowledge_model: str | Path,
    manifest_path: str | Path,
    output: str | Path,
    metadata: ReviewMetadata,
    project_name: str = "Translation Review",
) -> dict[str, Any]:
    """Seed the private disposable DSW and generate its public review policy."""
    api = DswApi(api_url)
    api.wait_until_ready()
    api.wait_until_operational(client_url)
    api.login(email, password)
    api.complete_tours()
    locale = api.install_locale(locale_bundle, default_locale=True)
    project_uuid = api.seed_project(knowledge_model, project_name=project_name)
    pages = generate_review_site(
        load_review_manifest(manifest_path),
        output,
        project_uuid=project_uuid,
        reviewer_email=email,
        reviewer_password=password,
        metadata=metadata,
    )
    result = {"projectUuid": project_uuid, "locale": locale, "pages": pages["pages"]}
    (Path(output) / "setup.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def latest_review_heartbeat(logs: str) -> float | None:
    """Return the newest browser heartbeat timestamp found in gateway logs."""
    timestamps = [float(match.group("timestamp")) for match in _HEARTBEAT_PATTERN.finditer(logs)]
    return max(timestamps, default=None)


def review_expiry_reason(
    *,
    now: float,
    started_at: float,
    last_activity_at: float,
    idle_timeout_seconds: float,
    hard_timeout_seconds: float,
) -> Literal["idle", "hard-limit"] | None:
    """Determine whether an ephemeral review has reached either lifetime limit."""
    if now - started_at >= hard_timeout_seconds:
        return "hard-limit"
    if now - last_activity_at >= idle_timeout_seconds:
        return "idle"
    return None


def _epoch_isoformat(value: float) -> str:
    return datetime.fromtimestamp(value, UTC).isoformat().replace("+00:00", "Z")


def wait_for_review(
    *,
    compose_file: str | Path,
    project_name: str,
    tunnel_container: str,
    idle_timeout_minutes: int,
    hard_timeout_minutes: int,
    poll_seconds: float = 30,
) -> dict[str, str]:
    """Keep a review alive while browsers are active and stop at its hard limit."""
    if (
        idle_timeout_minutes < 1
        or hard_timeout_minutes < idle_timeout_minutes
        or hard_timeout_minutes > 360
    ):
        raise LocaleToolError(
            "Review timeouts must be positive, ordered, and no longer than 360 minutes"
        )
    if poll_seconds <= 0 or poll_seconds > 300:
        raise LocaleToolError("Review poll interval must be between 0 and 300 seconds")

    compose_path = Path(compose_file)
    if not compose_path.is_file():
        raise LocaleToolError(f"Review Compose file does not exist: {compose_path}")

    started_at = time.time()
    last_activity_at = started_at
    while True:
        tunnel = subprocess.run(
            ["docker", "inspect", "--format={{.State.Running}}", tunnel_container],
            check=False,
            capture_output=True,
            text=True,
        )
        if tunnel.returncode != 0 or tunnel.stdout.strip() != "true":
            raise LocaleToolError("The public review tunnel stopped unexpectedly")

        gateway_logs = subprocess.run(
            [
                "docker",
                "compose",
                "--project-name",
                project_name,
                "--file",
                str(compose_path),
                "logs",
                "--no-color",
                "gateway",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if gateway_logs.returncode != 0:
            raise LocaleToolError("Unable to read review gateway activity")
        if (heartbeat := latest_review_heartbeat(gateway_logs.stdout)) is not None:
            last_activity_at = max(last_activity_at, heartbeat)

        now = time.time()
        reason = review_expiry_reason(
            now=now,
            started_at=started_at,
            last_activity_at=last_activity_at,
            idle_timeout_seconds=idle_timeout_minutes * 60,
            hard_timeout_seconds=hard_timeout_minutes * 60,
        )
        if reason:
            return {
                "reason": reason,
                "startedAt": _epoch_isoformat(started_at),
                "lastActivityAt": _epoch_isoformat(last_activity_at),
                "endedAt": _epoch_isoformat(now),
            }
        time.sleep(poll_seconds)


def verify_review_gateway(
    origin: str,
    *,
    email: str,
    password: str,
    timeout: float = 30,
    session: requests.Session | None = None,
) -> dict[str, int]:
    """Verify that review pages work and public mutation paths are denied."""
    base_url = origin.rstrip("/")
    client = session or requests.Session()

    def request(method: str, path: str, **kwargs: Any) -> requests.Response:
        try:
            return client.request(method, f"{base_url}{path}", timeout=timeout, **kwargs)
        except requests.RequestException as error:
            raise LocaleToolError(
                f"Review gateway request failed: {method} {path}: {error}"
            ) from error

    checks: dict[str, int] = {}
    deadline = time.monotonic() + timeout
    portal_error = "no response"
    while time.monotonic() < deadline:
        try:
            response = request("GET", "/")
            if response.ok:
                break
            portal_error = f"HTTP {response.status_code}"
        except LocaleToolError as error:
            portal_error = str(error)
        time.sleep(0.5)
    else:
        raise LocaleToolError(f"Review gateway did not become ready: {portal_error}")
    checks["portal"] = response.status_code

    heartbeat = request("POST", "/review/heartbeat")
    checks["heartbeat"] = heartbeat.status_code
    if heartbeat.status_code != 204:
        raise LocaleToolError(f"Review gateway heartbeat failed with HTTP {heartbeat.status_code}")

    for name, path in (("login-page", "/wizard/login"),):
        response = request("GET", path)
        checks[name] = response.status_code
        if not response.ok:
            raise LocaleToolError(f"Review gateway {name} failed with HTTP {response.status_code}")

    login = request(
        "POST",
        "/wizard-api/tokens",
        json={"email": email, "password": password},
    )
    checks["login"] = login.status_code
    if not login.ok or not (token := login.json().get("token")):
        raise LocaleToolError(f"Review gateway login failed with HTTP {login.status_code}")
    headers = {"Authorization": f"Bearer {token}"}

    current_user = request("GET", "/wizard-api/users/current", headers=headers)
    checks["read-api"] = current_user.status_code
    if not current_user.ok:
        raise LocaleToolError(
            f"Review gateway API read failed with HTTP {current_user.status_code}"
        )

    denied = (
        ("update-tour", "PUT", "/wizard-api/users/current/tours/dashboard", {}),
        ("create-project", "POST", "/wizard-api/projects", {"json": {}}),
        ("delete-token", "DELETE", "/wizard-api/tokens/current", {}),
        (
            "websocket",
            "GET",
            "/wizard-api/projects/review/websocket",
            {"headers": {**headers, "Upgrade": "websocket", "Connection": "Upgrade"}},
        ),
    )
    for name, method, path, kwargs in denied:
        request_headers = {**headers, **kwargs.pop("headers", {})}
        response = request(method, path, headers=request_headers, **kwargs)
        checks[name] = response.status_code
        if response.status_code != 403:
            raise LocaleToolError(
                f"Review gateway allowed {name}: expected HTTP 403, got {response.status_code}"
            )

    disallowed = request("GET", "/wizard/users")
    checks["disallowed-page"] = disallowed.status_code
    if disallowed.status_code != 404:
        raise LocaleToolError(
            "Review gateway exposed an unapproved UI route: "
            f"expected HTTP 404, got {disallowed.status_code}"
        )
    return checks
