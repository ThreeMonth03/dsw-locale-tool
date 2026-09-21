"""Discover official Weblate release lines and report local version drift."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

import requests

from dsw_locale_tool.config import TranslationConfig
from dsw_locale_tool.errors import LocaleToolError

WEBLATE_PROJECT_PATTERN = re.compile(r"^DSW (?P<major>\d+)\.(?P<minor>\d+)$")
WEBLATE_PROJECT_PATH_PATTERN = re.compile(
    r"^/projects/(?P<slug>dsw-(?P<major>\d+)-(?P<minor>\d+))/$"
)
WEBLATE_LOCK_TITLE = "This translation is locked."


@dataclass(frozen=True)
class WeblateVersion:
    """One DSW minor release line listed by the official Weblate instance."""

    version: str
    project: str
    slug: str
    locked: bool
    url: str

    @property
    def expected_state(self) -> str:
        """Map Weblate's lock state to the local lifecycle state."""
        return "maintenance" if self.locked else "active"


class WeblateProjectsParser(HTMLParser):
    """Extract DSW project versions and lock states from Weblate's public table."""

    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.in_row = False
        self.row_slug: str | None = None
        self.row_locked = False
        self.versions: dict[str, WeblateVersion] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "tr":
            self.in_row = True
            self.row_slug = None
            self.row_locked = False
            return
        if not self.in_row:
            return
        if tag == "a" and isinstance((href := attributes.get("href")), str):
            if match := WEBLATE_PROJECT_PATH_PATTERN.fullmatch(href):
                self.row_slug = match.group("slug")
        if attributes.get("title") == WEBLATE_LOCK_TITLE:
            self.row_locked = True

    def handle_endtag(self, tag: str) -> None:
        if tag != "tr" or not self.in_row:
            return
        if self.row_slug:
            match = WEBLATE_PROJECT_PATH_PATTERN.fullmatch(f"/projects/{self.row_slug}/")
            if match is not None:
                number = f"{match.group('major')}.{match.group('minor')}"
                version = f"v{number}"
                self.versions[version] = WeblateVersion(
                    version=version,
                    project=f"DSW {number}",
                    slug=self.row_slug,
                    locked=self.row_locked,
                    url=urljoin(f"{self.base_url}/", f"{self.row_slug}/"),
                )
        self.in_row = False
        self.row_slug = None
        self.row_locked = False


def version_sort_key(version: str) -> tuple[int, int]:
    major, minor = version.removeprefix("v").split(".", maxsplit=1)
    return int(major), int(minor)


def fetch_weblate_versions(
    config: TranslationConfig,
    *,
    session: Any = requests,
) -> list[WeblateVersion]:
    """Fetch all DSW projects with one request to the official Weblate API."""
    url = config.weblate.projects_url
    try:
        response = session.get(
            url,
            params={"page_size": 100},
            headers={"User-Agent": "dsw-locale-tool"},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as error:
        try:
            return fetch_public_weblate_versions(config, session=session)
        except LocaleToolError as fallback_error:
            raise LocaleToolError(
                f"{_weblate_request_error(error)}; public fallback also failed: {fallback_error}"
            ) from fallback_error
    except (TypeError, ValueError) as error:
        raise LocaleToolError(f"Weblate returned invalid JSON from {url}") from error

    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise LocaleToolError("Weblate project catalog has an unexpected response shape")
    if payload.get("next"):
        raise LocaleToolError(
            "Weblate project catalog contains more than 100 projects; refusing a partial report"
        )

    versions: dict[str, WeblateVersion] = {}
    for project in payload["results"]:
        if not isinstance(project, dict):
            continue
        name = project.get("name")
        if not isinstance(name, str) or not (match := WEBLATE_PROJECT_PATTERN.fullmatch(name)):
            continue
        version = f"v{match.group('major')}.{match.group('minor')}"
        slug = project.get("slug")
        locked = project.get("locked")
        web_url = project.get("web_url")
        if not isinstance(slug, str) or not isinstance(locked, bool):
            raise LocaleToolError(f"Weblate project {name!r} is missing slug or locked metadata")
        if not isinstance(web_url, str):
            web_url = f"https://localize.ds-wizard.org/projects/{slug}/"
        if version in versions:
            raise LocaleToolError(f"Weblate lists DSW {version.removeprefix('v')} more than once")
        versions[version] = WeblateVersion(version, name, slug, locked, web_url)

    if not versions:
        raise LocaleToolError("Weblate project catalog contains no DSW version projects")
    return sorted(versions.values(), key=lambda item: version_sort_key(item.version))


def _weblate_request_error(error: requests.RequestException) -> LocaleToolError:
    response = error.response
    retry_after = response.headers.get("Retry-After") if response is not None else None
    detail = f"; retry after {retry_after} seconds" if retry_after else ""
    return LocaleToolError(f"Unable to read Weblate project catalog{detail}: {error}")


def fetch_public_weblate_versions(
    config: TranslationConfig,
    *,
    session: Any = requests,
) -> list[WeblateVersion]:
    """Read Weblate's public project table when its rate-limited API is unavailable."""
    url = config.weblate.public_projects_url
    try:
        response = session.get(
            url,
            headers={"User-Agent": "dsw-locale-tool"},
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise LocaleToolError(f"Unable to read public Weblate project catalog: {error}") from error

    parser = WeblateProjectsParser(url)
    parser.feed(response.text)
    parser.close()
    if not parser.versions:
        raise LocaleToolError("Public Weblate project catalog contains no DSW version projects")
    return sorted(parser.versions.values(), key=lambda item: version_sort_key(item.version))
