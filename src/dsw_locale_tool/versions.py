"""Discover official Weblate release lines and report local version drift."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
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
            headers={"User-Agent": "dsw-locale-tool/0.1 (+version-catalog)"},
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
            headers={"User-Agent": "dsw-locale-tool/0.1 (+version-catalog-fallback)"},
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


def available_git_branches(repository_root: str | Path) -> set[str]:
    """Return local and fetched remote branch names from a translation checkout."""
    root = Path(repository_root).resolve()
    try:
        result = subprocess.run(
            [
                "git",
                "for-each-ref",
                "--format=%(refname)",
                "refs/heads",
                "refs/remotes",
            ],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise LocaleToolError("git is required to inspect translation branches") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or error.stdout.strip() or str(error)
        raise LocaleToolError(f"Unable to inspect translation branches: {detail}") from error
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _branch_is_present(branch: str, refs: set[str]) -> bool:
    suffix = f"/{branch}"
    return any(ref.endswith(suffix) for ref in refs)


def build_version_report(
    config: TranslationConfig,
    official_versions: Iterable[WeblateVersion],
    *,
    branch_refs: set[str] | None = None,
) -> dict[str, Any]:
    """Compare Weblate, translation configuration, and optional Git branches."""
    official = {item.version: item for item in official_versions}
    configured = config.versions
    missing_versions = sorted(set(official) - set(configured), key=version_sort_key)
    state_mismatches: list[dict[str, str]] = []
    official_rows: list[dict[str, Any]] = []
    missing_branches: list[str] = []

    for version_key in sorted(official, key=version_sort_key):
        item = official[version_key]
        branch = f"{config.branches.version_prefix}{version_key}"
        local = configured.get(version_key)
        branch_present = None if branch_refs is None else _branch_is_present(branch, branch_refs)
        if branch_present is False:
            missing_branches.append(branch)
        if local is not None and local.state != item.expected_state:
            state_mismatches.append(
                {
                    "version": version_key,
                    "expected": item.expected_state,
                    "actual": local.state,
                }
            )
        official_rows.append(
            {
                "version": version_key,
                "project": item.project,
                "slug": item.slug,
                "url": item.url,
                "weblate_locked": item.locked,
                "expected_state": item.expected_state,
                "configured_state": local.state if local else None,
                "expected_branch": branch,
                "branch_present": branch_present,
            }
        )

    configured_only = sorted(set(configured) - set(official), key=version_sort_key)
    missing_from_weblate = [
        version for version in configured_only if configured[version].state != "retired"
    ]
    archived_versions = [
        version for version in configured_only if configured[version].state == "retired"
    ]
    drift = {
        "missing_versions": missing_versions,
        "state_mismatches": state_mismatches,
        "missing_branches": missing_branches,
        "missing_from_weblate": missing_from_weblate,
    }
    return {
        "schema_version": 1,
        "source": config.weblate.projects_url,
        "aligned": not any(drift.values()),
        "official_versions": official_rows,
        "archived_versions": archived_versions,
        "drift": drift,
    }


def render_version_report(report: dict[str, Any]) -> str:
    """Render a concise Markdown report suitable for Actions job summaries."""
    lines = [
        "# DSW version alignment",
        "",
        f"Status: **{'aligned' if report['aligned'] else 'drift detected'}**",
        "",
        "| Version | Weblate | Expected state | Config state | Branch |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in report["official_versions"]:
        locked = "locked" if item["weblate_locked"] else "open"
        branch_status = item["expected_branch"]
        if item["branch_present"] is False:
            branch_status += " (missing)"
        lines.append(
            f"| {item['version']} | {locked} | {item['expected_state']} | "
            f"{item['configured_state'] or 'missing'} | `{branch_status}` |"
        )

    drift = report["drift"]
    lines.extend(["", "## Drift", ""])
    if report["aligned"]:
        lines.append("No version drift detected.")
    else:
        if drift["missing_versions"]:
            lines.append(f"- Missing from config: {', '.join(drift['missing_versions'])}")
        for item in drift["state_mismatches"]:
            lines.append(
                f"- {item['version']} state is `{item['actual']}`; expected `{item['expected']}`."
            )
        if drift["missing_branches"]:
            lines.append(f"- Missing branches: {', '.join(drift['missing_branches'])}")
        if drift["missing_from_weblate"]:
            lines.append(
                "- Active/maintenance versions absent from Weblate: "
                + ", ".join(drift["missing_from_weblate"])
            )
    if report["archived_versions"]:
        lines.extend(
            [
                "",
                "Archived versions retained locally: " + ", ".join(report["archived_versions"]),
            ]
        )
    return "\n".join(lines) + "\n"


def write_version_report(report: dict[str, Any], output_directory: str | Path) -> tuple[Path, Path]:
    """Write machine-readable and reviewer-friendly version reports."""
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "versions.json"
    markdown_path = output / "versions.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_version_report(report), encoding="utf-8")
    return json_path, markdown_path
