"""Browser verification configuration tests."""

from __future__ import annotations

import pytest

from dsw_locale_tool.errors import LocaleToolError
from dsw_locale_tool.review_browser import _dashboard_path


def test_dashboard_path_comes_from_the_generated_review_configuration():
    assert (
        _dashboard_path(
            {
                "pages": [
                    {"name": "login", "path": "/wizard/login"},
                    {"name": "dashboard", "path": "/wizard/dashboard"},
                ]
            }
        )
        == "/wizard/dashboard"
    )


@pytest.mark.parametrize(
    "payload",
    (
        {},
        {"pages": []},
        {"pages": [{"name": "dashboard", "path": "/"}]},
        {
            "pages": [
                {"name": "dashboard", "path": "/wizard/dashboard"},
                {"name": "dashboard", "path": "/wizard/other"},
            ]
        },
    ),
)
def test_dashboard_path_rejects_missing_duplicate_or_external_routes(payload):
    with pytest.raises(LocaleToolError):
        _dashboard_path(payload)
