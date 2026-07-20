"""Browser-level verification for a public DSW translation review."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import requests

from dsw_locale_tool.errors import LocaleToolError


def _dashboard_path(payload: Any) -> str:
    if not isinstance(payload, dict) or not isinstance(payload.get("pages"), list):
        raise LocaleToolError("Review configuration does not contain a page list")
    dashboards = [
        page
        for page in payload["pages"]
        if isinstance(page, dict) and page.get("name") == "dashboard"
    ]
    if len(dashboards) != 1 or not isinstance(dashboards[0].get("path"), str):
        raise LocaleToolError("Review configuration must contain one dashboard page")
    path = dashboards[0]["path"]
    parts = urlsplit(path)
    if not path.startswith("/wizard/") or parts.query or parts.fragment:
        raise LocaleToolError("Review dashboard path is invalid")
    return path


def verify_review_browser(
    origin: str,
    *,
    email: str,
    password: str,
    timeout: float = 60,
) -> dict[str, str]:
    """Sign in through the real UI and require a stable, visible dashboard."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise LocaleToolError(
            "Browser review verification requires: pip install 'dsw-locale-tool[preview]'"
        ) from error

    base_url = origin.rstrip("/")
    try:
        response = requests.get(f"{base_url}/review/review.json", timeout=timeout)
        response.raise_for_status()
        dashboard_path = _dashboard_path(response.json())
    except requests.RequestException as error:
        raise LocaleToolError(f"Unable to load the public review configuration: {error}") from error
    except requests.JSONDecodeError as error:
        raise LocaleToolError("Public review configuration is not valid JSON") from error

    timeout_ms = int(timeout * 1000)
    page_errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(
                f"{base_url}/wizard/login",
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
            page.locator("#email").fill(email, timeout=timeout_ms)
            page.locator("#password").fill(password, timeout=timeout_ms)
            page.locator('[data-cy="form_submit"]').click(timeout=timeout_ms)
            page.wait_for_url(
                f"{base_url}{dashboard_path}",
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
            page.locator("#dsw-review-banner").wait_for(
                state="visible",
                timeout=timeout_ms,
            )
            body_text = page.locator("body").inner_text(timeout=timeout_ms).strip()
            current_url = page.url
            browser.close()
    except Exception as error:  # Playwright is an optional runtime dependency.
        raise LocaleToolError(
            f"Review browser could not render the dashboard at {dashboard_path}"
        ) from error

    if page_errors:
        raise LocaleToolError(f"Review dashboard raised a browser error: {page_errors[0]}")
    if len(body_text) < 50:
        raise LocaleToolError("Review dashboard rendered without visible interface content")
    return {"dashboardPath": dashboard_path, "dashboardUrl": current_url}
