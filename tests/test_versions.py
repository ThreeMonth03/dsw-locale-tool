"""Official Weblate version catalog and drift report tests."""

from __future__ import annotations

from dsw_locale_tool.versions import (
    WeblateVersion,
    build_version_report,
    fetch_weblate_versions,
    render_version_report,
)
from tests.conftest import make_config


class FakeResponse:
    """Minimal requests response used to keep tests offline."""

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    """Record calls and return one project catalog fixture."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payload)


def _version(version: str, *, locked: bool) -> WeblateVersion:
    number = version.removeprefix("v")
    slug = f"dsw-{number.replace('.', '-')}"
    return WeblateVersion(
        version=version,
        project=f"DSW {number}",
        slug=slug,
        locked=locked,
        url=f"https://localize.ds-wizard.org/projects/{slug}/",
    )


def test_fetch_weblate_versions_uses_one_request_and_filters_other_projects():
    session = FakeSession(
        {
            "next": None,
            "results": [
                {"name": "Glossary", "slug": "glossary", "locked": False},
                {"name": "DSW 4.32", "slug": "dsw-4-32", "locked": False},
                {"name": "DSW 4.31", "slug": "dsw-4-31", "locked": True},
            ],
        }
    )

    versions = fetch_weblate_versions(make_config(), session=session)

    assert [item.version for item in versions] == ["v4.31", "v4.32"]
    assert [item.expected_state for item in versions] == ["maintenance", "active"]
    assert len(session.calls) == 1
    assert session.calls[0][1]["params"] == {"page_size": 100}


def test_version_report_detects_missing_config_state_and_branches():
    config = make_config()
    config.versions["v4.32"].state = "maintenance"
    official = [_version("v4.29", locked=True), _version("v4.32", locked=False)]
    refs = {"refs/remotes/origin/sync/v4.32"}

    report = build_version_report(config, official, branch_refs=refs)

    assert report["aligned"] is False
    assert report["drift"]["missing_versions"] == ["v4.29"]
    assert report["drift"]["missing_branches"] == ["sync/v4.29"]
    assert report["drift"]["state_mismatches"] == [
        {"version": "v4.32", "expected": "active", "actual": "maintenance"}
    ]
    assert "drift detected" in render_version_report(report)


def test_retired_version_absent_from_weblate_is_preserved_without_drift():
    config = make_config()
    config.versions["v4.31"] = config.versions["v4.32"].model_copy(
        update={
            "upstream_ref": "v4.31",
            "locale_version": "4.31.0",
            "recommended_app_version": "4.31.0",
            "state": "retired",
        }
    )

    report = build_version_report(config, [_version("v4.32", locked=False)])

    assert report["aligned"] is True
    assert report["archived_versions"] == ["v4.31"]
