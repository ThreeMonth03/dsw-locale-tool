"""Small, version-focused client for DSW preview and locale deployment APIs."""

from __future__ import annotations

import json
import time
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests

from dsw_locale_tool.errors import LocaleToolError


def read_bundle_metadata(bundle: str | Path) -> dict[str, Any]:
    """Read the packaged ``locale/locale.json`` without extracting the ZIP."""
    bundle_path = Path(bundle)
    if not bundle_path.is_file():
        raise LocaleToolError(f"Locale bundle does not exist: {bundle_path}")
    try:
        with zipfile.ZipFile(bundle_path) as archive:
            return json.loads(archive.read("locale/locale.json"))
    except (KeyError, OSError, zipfile.BadZipFile, json.JSONDecodeError) as error:
        raise LocaleToolError(f"Invalid DSW locale bundle {bundle_path}: {error}") from error


class DswApi:
    """Authenticated DSW API operations needed by preview and deployment."""

    def __init__(
        self,
        api_url: str,
        *,
        timeout: float = 30,
        session: requests.Session | None = None,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.token: str | None = None

    @property
    def health_url(self) -> str:
        """Derive the server root used by official DSW end-to-end readiness checks."""
        parts = urlsplit(self.api_url)
        path = parts.path
        if path.endswith("/wizard-api"):
            path = path[: -len("/wizard-api")] or "/"
        else:
            path = "/"
        return urlunsplit((parts.scheme, parts.netloc, path, "", ""))

    def wait_until_ready(self, *, wait_timeout: float = 300, interval: float = 2) -> None:
        """Wait until the DSW server responds and its initial migrations finish."""
        deadline = time.monotonic() + wait_timeout
        last_error = "no response"
        while time.monotonic() < deadline:
            try:
                response = self.session.get(self.health_url, timeout=min(self.timeout, 5))
                if response.status_code < 500:
                    return
                last_error = f"HTTP {response.status_code}"
            except requests.RequestException as error:
                last_error = str(error)
            time.sleep(interval)
        raise LocaleToolError(
            f"DSW did not become ready within {wait_timeout:g} seconds: {last_error}"
        )

    def wait_until_operational(
        self,
        client_url: str,
        *,
        wait_timeout: float = 300,
        interval: float = 2,
    ) -> None:
        """Wait for DSW's asynchronous housekeeping to finish."""
        deadline = time.monotonic() + wait_timeout
        last_state = "no response"
        while time.monotonic() < deadline:
            try:
                response = self.session.get(
                    f"{self.api_url}/configs/bootstrap",
                    params={"clientUrl": client_url},
                    timeout=min(self.timeout, 5),
                )
                if response.ok:
                    state = response.json().get("type")
                    if state != "HousekeepingInProgressClientConfig":
                        return
                    last_state = state
                else:
                    last_state = f"HTTP {response.status_code}"
            except (requests.RequestException, ValueError) as error:
                last_state = str(error)
            time.sleep(interval)
        raise LocaleToolError(
            f"DSW housekeeping did not finish within {wait_timeout:g} seconds: {last_state}"
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        headers = dict(kwargs.pop("headers", {}))
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            response = self.session.request(
                method,
                f"{self.api_url}/{path.lstrip('/')}",
                headers=headers,
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as error:
            raise LocaleToolError(f"DSW API request failed: {method} {path}: {error}") from error
        if not response.ok:
            detail = response.text.strip().replace("\n", " ")[:500]
            raise LocaleToolError(
                f"DSW API request failed: {method} {path}: HTTP {response.status_code}: {detail}"
            )
        return response

    def login(self, email: str, password: str) -> str:
        """Create a DSW user token and attach it to subsequent requests."""
        response = self._request("POST", "/tokens", json={"email": email, "password": password})
        token = response.json().get("token")
        if not token:
            raise LocaleToolError("DSW token response did not contain a token")
        self.token = token
        return token

    def use_api_key(self, api_key: str) -> None:
        """Attach a pre-created DSW API key to subsequent requests."""
        if not api_key.strip():
            raise LocaleToolError("DSW API key cannot be empty")
        self.token = api_key.strip()

    def current_user(self) -> dict[str, Any]:
        """Return the authenticated user used by browser preview."""
        return self._request("GET", "/users/current").json()

    def complete_tours(self) -> None:
        """Mark built-in onboarding tours complete so screenshots show the underlying UI."""
        tour_ids = (
            "dashboard",
            "projects_create",
            "projects_detail",
            "projects_detail_share-modal",
            "projects_index",
            "users_edit_tours",
        )
        for tour_id in tour_ids:
            self._request("PUT", f"/users/current/tours/{tour_id}")

    def find_locale(self, metadata: dict[str, Any]) -> dict[str, Any] | None:
        """Find the exact locale coordinate when an installer job is rerun."""
        response = self._request(
            "GET",
            "/locales",
            params={
                "organizationId": metadata["organizationId"],
                "localeId": metadata["localeId"],
                "size": 1000,
            },
        ).json()
        for locale in response.get("_embedded", {}).get("locales", []):
            if locale.get("version") == metadata["version"]:
                return locale
        return None

    def install_locale(self, bundle: str | Path, *, default_locale: bool) -> dict[str, Any]:
        """Idempotently import, enable, and optionally make a locale the default."""
        bundle_path = Path(bundle)
        metadata = read_bundle_metadata(bundle_path)
        locale = self.find_locale(metadata)
        created = locale is None
        if created:
            with bundle_path.open("rb") as bundle_file:
                locale = self._request(
                    "POST",
                    "/locales/bundle",
                    files={
                        "file": (
                            bundle_path.name,
                            bundle_file,
                            "application/zip",
                        )
                    },
                ).json()

        locale_uuid = locale.get("uuid") if locale else None
        if not locale_uuid:
            raise LocaleToolError("DSW locale response did not contain a UUID")
        updated = self._request(
            "PUT",
            f"/locales/{locale_uuid}",
            json={"enabled": True, "defaultLocale": default_locale},
        ).json()
        return {
            "created": created,
            "id": metadata.get("id"),
            "uuid": locale_uuid,
            "enabled": updated.get("enabled", True),
            "defaultLocale": updated.get("defaultLocale", default_locale),
        }

    def seed_project(
        self,
        knowledge_model: str | Path,
        *,
        project_name: str = "Locale Preview",
    ) -> str:
        """Import a KM JSON bundle and create a private project for UI screenshots."""
        package_path = Path(knowledge_model)
        if not package_path.is_file():
            raise LocaleToolError(f"Knowledge Model package does not exist: {package_path}")
        try:
            package = json.loads(package_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise LocaleToolError(
                f"Invalid Knowledge Model JSON {package_path}: {error}"
            ) from error

        package_response = self._request("POST", "/knowledge-model-packages", json=package).json()
        package_uuid = package_response.get("uuid")
        if not package_uuid:
            raise LocaleToolError("DSW Knowledge Model import did not return a UUID")

        project = self._request(
            "POST",
            "/projects",
            json={
                "name": project_name,
                "knowledgeModelPackageUuid": package_uuid,
                "visibility": "PrivateProjectVisibility",
                "sharing": "RestrictedProjectSharing",
                "questionTagUuids": [],
                "documentTemplateUuid": None,
                "formatUuid": None,
            },
        ).json()
        project_uuid = project.get("uuid")
        if not project_uuid:
            raise LocaleToolError("DSW project creation did not return a UUID")
        return project_uuid
