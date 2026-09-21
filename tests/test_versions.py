"""Official Weblate version catalog and drift report tests."""

from __future__ import annotations

import requests

from dsw_locale_tool.versions import (
    fetch_weblate_versions,
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


class RateLimitedSession:
    """Return an API 429 followed by a successful public projects page."""

    def __init__(self, html: str):
        self.html = html
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if len(self.calls) == 1:
            response = requests.Response()
            response.status_code = 429
            response.headers["Retry-After"] = "1000"
            response.url = url
            return response
        response = requests.Response()
        response.status_code = 200
        response.url = url
        response._content = self.html.encode()
        response.encoding = "utf-8"
        return response


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


def test_fetch_weblate_versions_falls_back_to_public_page_after_rate_limit():
    session = RateLimitedSession(
        """
        <table>
          <tr>
            <th><a href="/projects/dsw-4-31/">DSW 4.31</a>
              <span title="This translation is locked."></span></th>
          </tr>
          <tr><th><a href="/projects/dsw-4-32/">DSW 4.32</a></th></tr>
          <tr><th><a href="/projects/glossary/">Glossary</a></th></tr>
        </table>
        """
    )

    versions = fetch_weblate_versions(make_config(), session=session)

    assert [item.version for item in versions] == ["v4.31", "v4.32"]
    assert [item.expected_state for item in versions] == ["maintenance", "active"]
    assert versions[0].url == "https://localize.ds-wizard.org/projects/dsw-4-31/"
    assert [call[0] for call in session.calls] == [
        "https://localize.ds-wizard.org/api/projects/",
        "https://localize.ds-wizard.org/projects/",
    ]
