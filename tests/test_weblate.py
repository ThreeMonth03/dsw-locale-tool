"""Validate API request boundaries without a Weblate account."""

import pytest
import requests

from dsw_locale_tool.errors import LocaleToolError
from dsw_locale_tool.weblate import ORIGIN, WeblateClient


class Session:
    def __init__(self, payload=None, status=200):
        self.payload = payload
        self.status = status
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = requests.Response()
        response.status_code = self.status
        response.url = url
        response.json = lambda: self.payload
        return response


def unit(client):
    return {
        "id": 1,
        "translation": client.translation_url("wizard"),
        "source": ["Save"],
        "context": "",
        "target": [""],
        "state": 0,
    }


def test_token_is_not_sent_to_untrusted_host():
    session = Session()
    client = WeblateClient("v4.34", "secret", session=session)
    with pytest.raises(LocaleToolError, match="outside"):
        client.json("GET", "https://example.test/api/units/1/")
    assert not session.calls


def test_authenticated_redirect_is_not_followed():
    session = Session(status=302)
    client = WeblateClient("v4.34", "secret", session=session)
    with pytest.raises(LocaleToolError, match="redirected"):
        client.get_unit(1, "wizard")
    assert session.calls[0][2]["allow_redirects"] is False


def test_only_target_and_fuzzy_state_are_written():
    session = Session({})
    WeblateClient("v4.34", "secret", session=session).set_fuzzy(1, "儲存")
    method, url, kwargs = session.calls[0]
    assert method == "PATCH"
    assert url == ORIGIN + "/api/units/1/"
    assert kwargs["json"] == {"target": ["儲存"], "state": 10}


@pytest.mark.parametrize("foreign", ["en", "fr", "zh_Hans"])
def test_foreign_language_unit_is_rejected(foreign):
    client = WeblateClient("v4.34")
    record = unit(client)
    record["translation"] = record["translation"].replace("zh_Hant", foreign)
    with pytest.raises(LocaleToolError, match="outside"):
        client.validate_unit(record, "wizard")


def test_pagination_cannot_leave_selected_translation():
    session = Session({"results": [], "next": ORIGIN + "/api/translations/other/client/en/units/"})
    client = WeblateClient("v4.34", "secret", session=session)
    with pytest.raises(LocaleToolError, match="pagination"):
        client.units("wizard")
    assert len(session.calls) == 1


def test_error_does_not_expose_token():
    client = WeblateClient("v4.34", "never-log-this", session=Session(status=403))
    with pytest.raises(LocaleToolError) as error:
        client.get_unit(1, "wizard")
    assert "never-log-this" not in str(error.value)
    assert "403" in str(error.value)
