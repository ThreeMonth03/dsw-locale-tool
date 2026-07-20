"""Validated page policy and runtime helpers for the public review sandbox."""

from __future__ import annotations

import json
import re
import shutil
import time
from collections import Counter
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

    @model_validator(mode="after")
    def validate_project_requirement(self) -> ReviewPage:
        if (_PROJECT_PLACEHOLDER in self.route) != self.requires_project:
            raise ValueError("requires_project must match use of {project_uuid} in route")
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
        for label, values in (
            ("page name", [page.name for page in self.pages]),
            ("page route", [page.route for page in self.pages]),
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
        "pages": public_pages,
        "allowedPaths": [page["path"] for page in public_pages],
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
    )
    result = {"projectUuid": project_uuid, "locale": locale, "pages": pages["pages"]}
    (Path(output) / "setup.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


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
