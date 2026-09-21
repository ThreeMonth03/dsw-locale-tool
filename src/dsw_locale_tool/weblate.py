"""Scoped access to the official DSW Weblate instance."""

from __future__ import annotations

from urllib.parse import urlparse

import polib
import requests

from dsw_locale_tool.catalog import MALFORMED_TRANSLATOR_COMMENT
from dsw_locale_tool.config import VERSION_KEY_PATTERN
from dsw_locale_tool.errors import LocaleToolError

ORIGIN = "https://localize.ds-wizard.org"
COMPONENT_SLUGS = {"wizard": "client", "mail": "mail-templates"}


class WeblateClient:
    """No configurable write host, source-language writes, or automatic write retries."""

    def __init__(self, version: str, token: str | None = None, *, session=None):
        if not VERSION_KEY_PATTERN.fullmatch(version):
            raise LocaleToolError(f"Invalid DSW version: {version!r}")
        self.project = "dsw-" + version.removeprefix("v").replace(".", "-")
        self.session = session or requests.Session()
        self.token = token

    def translation_url(self, component: str) -> str:
        return f"{ORIGIN}/api/translations/{self.project}/{COMPONENT_SLUGS[component]}/zh_Hant/"

    def _request(self, method: str, url: str, **kwargs):
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != "localize.ds-wizard.org":
            raise LocaleToolError("Refusing a request outside official DSW Weblate")
        headers = {"User-Agent": "dsw-locale-tool"}
        if self.token and parsed.path.startswith("/api/"):
            headers["Authorization"] = f"Token {self.token}"
        try:
            response = self.session.request(
                method, url, headers=headers, timeout=30, allow_redirects=False, **kwargs
            )
            response.raise_for_status()
            if 300 <= response.status_code < 400:
                raise LocaleToolError("Weblate redirected a scoped request")
            return response
        except requests.RequestException as error:
            status = error.response.status_code if error.response is not None else "network error"
            # Never include request headers, token, or a raw response body in logs.
            raise LocaleToolError(f"Weblate {method} failed ({status})") from None

    def json(self, method: str, url: str, **kwargs):
        try:
            return self._request(method, url, **kwargs).json()
        except ValueError:
            raise LocaleToolError("Weblate returned invalid JSON") from None

    def catalog(self, component: str) -> polib.POFile:
        url = f"{ORIGIN}/download/{self.project}/{COMPONENT_SLUGS[component]}/zh_Hant/"
        text = self._request("GET", url).content.decode("utf-8-sig")
        try:
            catalog = polib.pofile(MALFORMED_TRANSLATOR_COMMENT.sub("# ", text))
        except (ValueError, OSError):
            raise LocaleToolError("Weblate returned an invalid PO file") from None
        if catalog.metadata.get("Language") != "zh_Hant" or not catalog:
            raise LocaleToolError("Weblate download is not a Traditional Chinese catalog")
        return catalog

    def units(self, component: str) -> list[dict]:
        base = self.translation_url(component) + "units/"
        url = base + "?page_size=200"
        seen = set()
        units = []
        while url:
            if url in seen or url.split("?")[0] != base:
                raise LocaleToolError("Invalid Weblate pagination URL")
            seen.add(url)
            page = self.json("GET", url)
            if not isinstance(page, dict) or not isinstance(page.get("results"), list):
                raise LocaleToolError("Invalid Weblate units response")
            for unit in page["results"]:
                self.validate_unit(unit, component)
                units.append(unit)
            url = page.get("next")
        return units

    def validate_unit(self, unit: dict, component: str) -> None:
        if (
            not isinstance(unit, dict)
            or unit.get("translation") != self.translation_url(component)
            or type(unit.get("id")) is not int
            or not isinstance(unit.get("source"), list)
            or not isinstance(unit.get("target"), list)
            or not all(isinstance(s, str) for s in unit["source"] + unit["target"])
        ):
            raise LocaleToolError("Weblate unit is outside the selected translation or malformed")

    def get_unit(self, unit_id: int, component: str) -> dict:
        unit = self.json("GET", f"{ORIGIN}/api/units/{unit_id}/")
        self.validate_unit(unit, component)
        if unit["id"] != unit_id:
            raise LocaleToolError("Weblate returned a different unit ID")
        return unit

    def set_fuzzy(self, unit_id: int, translation: str) -> None:
        if not self.token:
            raise LocaleToolError("LOCALIZE_API_TOKEN is required to upload translations")
        self.json(
            "PATCH", f"{ORIGIN}/api/units/{unit_id}/", json={"target": [translation], "state": 10}
        )


def api_identity(unit: dict) -> tuple[str | None, str, str | None]:
    source = unit["source"]
    if len(source) not in (1, 2):
        raise LocaleToolError("Unexpected number of source plural forms")
    return unit.get("context") or None, source[0], source[1] if len(source) == 2 else None
