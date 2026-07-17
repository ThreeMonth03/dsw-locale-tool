"""Ephemeral DSW configuration and browser screenshot helpers."""

from __future__ import annotations

import json
import secrets
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from dsw_locale_tool.dsw import DswApi
from dsw_locale_tool.errors import LocaleToolError
from dsw_locale_tool.runtime import (
    classify_runtime_observations,
    load_allowed_content,
    write_runtime_report,
)


class _LiteralDumper(yaml.SafeDumper):
    pass


def _represent_string(dumper: yaml.SafeDumper, value: str) -> yaml.Node:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_LiteralDumper.add_representer(str, _represent_string)


@dataclass(frozen=True)
class _InteractiveScenario:
    name: str
    route: str
    trigger: str
    ready: str
    trigger_first: bool = False


def _authenticated_routes(project_uuid: str | None) -> dict[str, str]:
    routes = {
        "dashboard": "/",
        "projects": "/projects",
        "locales": "/locales",
    }
    if project_uuid:
        routes.update(
            {
                "questionnaire": f"/projects/{project_uuid}",
                "project-settings": f"/projects/{project_uuid}/settings",
            }
        )
    return routes


def _interactive_scenarios(project_uuid: str | None) -> tuple[_InteractiveScenario, ...]:
    if not project_uuid:
        return ()
    project_route = f"/projects/{project_uuid}"
    return (
        _InteractiveScenario(
            name="project-share-dialog",
            route=project_route,
            trigger='[data-cy="project_detail_share-button"]',
            ready='.modal.visible [data-cy="modal_project-share"]',
        ),
        _InteractiveScenario(
            name="question-comment-panel",
            route=project_route,
            trigger='[data-cy="questionnaire_question-action_comment"]',
            ready='[data-cy="comments_reply-form_input_new_public"]',
            trigger_first=True,
        ),
        _InteractiveScenario(
            name="project-delete-dialog",
            route=f"{project_route}/settings",
            trigger=".card.border-danger button.btn-outline-danger",
            ready='.modal.visible [data-cy="modal_project-delete"]',
        ),
    )


def generate_preview_config(output: str | Path, *, client_url: str) -> Path:
    """Generate secrets and a minimal DSW server configuration for an ephemeral stack."""
    try:
        result = subprocess.run(
            ["openssl", "genrsa", "-traditional", "2048"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise LocaleToolError("openssl is required to generate the preview RSA key") from error
    except subprocess.CalledProcessError as error:
        raise LocaleToolError(f"openssl failed to generate an RSA key: {error.stderr}") from error

    config = {
        "general": {
            "environment": "Production",
            "serverPort": 3000,
            "clientUrl": client_url,
            "secret": secrets.token_hex(16),
            "rsaPrivateKey": result.stdout,
        },
        "database": {
            "connectionString": "postgresql://postgres:postgres@postgres:5432/engine-wizard"
        },
        "s3": {
            "url": "http://minio:9000",
            "username": "minio",
            "password": "minioPassword",
            "bucket": "engine-wizard",
            "region": "local",
        },
        "mail": {
            "enabled": False,
            "name": None,
            "email": None,
            "provider": "smtp",
            "smtp": {
                "host": None,
                "port": None,
                "security": "plain",
                "username": None,
                "password": None,
            },
        },
        "cloud": {"enabled": False, "publicRegistrationEnabled": False},
    }
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.dump(config, Dumper=_LiteralDumper, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return output_path


def _wait_for_application(page: Any) -> None:
    """Wait until Elm has mounted and the active page has finished loading."""
    try:
        page.locator("body > :not(script)").first.wait_for(state="visible", timeout=30_000)
        for selector in (".full-page-loader", ".page-loader"):
            page.locator(selector).first.wait_for(state="hidden", timeout=30_000)
    except Exception as error:  # Playwright timeout types are optional at import time.
        raise LocaleToolError(f"DSW browser UI did not become ready: {page.url}") from error


def _wait_for_page_available(page: Any, name: str) -> None:
    """Wait for initial routing, then reject a stable DSW error page."""
    markers = {
        "not-found": "route was not found",
        "not-allowed": "preview account is not allowed to view the route",
        "error": "DSW rendered a full-page error",
    }
    not_found = page.locator('[data-cy="illustrated-message_not-found"]')
    if not_found.is_visible():
        try:
            not_found.wait_for(state="hidden", timeout=30_000)
        except Exception as error:  # Playwright timeout types are optional at import time.
            raise LocaleToolError(
                f"Cannot capture {name}: route was not found: {page.url}"
            ) from error
        _wait_for_application(page)

    for marker, description in markers.items():
        if page.locator(f'[data-cy="illustrated-message_{marker}"]').is_visible():
            raise LocaleToolError(f"Cannot capture {name}: {description}: {page.url}")


def _collect_visible_text(page: Any, route: str) -> list[dict[str, str]]:
    """Collect visible text nodes and user-facing attributes without parent duplicates."""
    records = page.evaluate(
        r"""
        () => {
          const normalize = (value) => value.replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
          const visible = (element) => {
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            const modal = element.closest(".modal");
            if (modal && !modal.classList.contains("visible") &&
                !modal.classList.contains("show")) return false;
            return style.display !== "none" && style.visibility !== "hidden" &&
              style.opacity !== "0" && rect.width > 0 && rect.height > 0 &&
              !element.closest('[aria-hidden="true"]');
          };
          const selector = (element) => {
            if (element.dataset.cy) {
              return `[data-cy="${CSS.escape(element.dataset.cy)}"]`;
            }
            if (element.id) {
              return `#${CSS.escape(element.id)}`;
            }
            const parts = [];
            let current = element;
            while (current && current !== document.body) {
              let part = current.tagName.toLowerCase();
              const siblings = current.parentElement
                ? [...current.parentElement.children].filter(
                    (item) => item.tagName === current.tagName
                  )
                : [];
              if (siblings.length > 1) {
                part += `:nth-of-type(${siblings.indexOf(current) + 1})`;
              }
              parts.unshift(part);
              current = current.parentElement;
            }
            return `body > ${parts.join(" > ")}`;
          };
          const records = [];
          const add = (element, kind, value) => {
            const text = normalize(value || "");
            if (text) {
              records.push({ text, kind, selector: selector(element) });
            }
          };
          for (const element of document.body.querySelectorAll("*")) {
            if (!visible(element)) continue;
            for (const node of element.childNodes) {
              if (node.nodeType === Node.TEXT_NODE) add(element, "text", node.textContent);
            }
            for (const attribute of ["placeholder", "aria-label", "title"]) {
              if (element.hasAttribute(attribute)) {
                add(element, attribute, element.getAttribute(attribute));
              }
            }
            if (element instanceof HTMLInputElement &&
                ["button", "submit", "reset"].includes(element.type)) {
              add(element, "value", element.value);
            }
            if (element instanceof HTMLSelectElement && element.selectedOptions.length) {
              add(element, "selected-option", element.selectedOptions[0].textContent);
            }
          }
          return records;
        }
        """
    )
    return [
        {
            "route": route,
            "url": page.url,
            "text": item["text"],
            "kind": item["kind"],
            "selector": item["selector"],
        }
        for item in records
    ]


def _user_content(user: dict[str, Any]) -> set[str]:
    values = {
        value
        for key in ("firstName", "lastName", "name", "email")
        if isinstance((value := user.get(key)), str) and value
    }
    first_name = user.get("firstName")
    last_name = user.get("lastName")
    if isinstance(first_name, str) and isinstance(last_name, str):
        values.add(f"{first_name} {last_name}")
    return values


def _capture_page(
    page: Any,
    *,
    name: str,
    output_path: Path,
    report: dict[str, Any],
    observations: list[dict[str, str]],
    full_page: bool,
) -> None:
    screenshot_path = output_path / f"{name}.png"
    page.screenshot(path=screenshot_path, full_page=full_page)
    observations.extend(_collect_visible_text(page, name))
    report["screenshots"].append({"name": name, "url": page.url, "file": screenshot_path.name})


def _capture_interactive_scenario(
    page: Any,
    *,
    base_url: str,
    scenario: _InteractiveScenario,
    output_path: Path,
    report: dict[str, Any],
    observations: list[dict[str, str]],
) -> None:
    page.goto(
        f"{base_url}{scenario.route}",
        wait_until="domcontentloaded",
        timeout=60_000,
    )
    _wait_for_application(page)
    _wait_for_page_available(page, scenario.name)
    trigger = page.locator(scenario.trigger)
    if scenario.trigger_first:
        trigger = trigger.first
    try:
        trigger.scroll_into_view_if_needed(timeout=30_000)
        trigger.click(timeout=30_000)
        ready = page.locator(scenario.ready)
        ready.wait_for(state="visible", timeout=30_000)
        ready.evaluate(
            """
            async (element) => {
              const root = element.closest(".modal") || element;
              const animations = root.getAnimations({ subtree: true });
              await Promise.all(
                animations.map((animation) => animation.finished.catch(() => undefined))
              );
            }
            """
        )
    except Exception as error:  # Playwright timeout types are optional at import time.
        raise LocaleToolError(
            f"Cannot capture {scenario.name}: interactive control was unavailable: {page.url}"
        ) from error
    _capture_page(
        page,
        name=scenario.name,
        output_path=output_path,
        report=report,
        observations=observations,
        full_page=False,
    )


def capture_preview(
    *,
    client_url: str,
    api_url: str,
    email: str,
    password: str,
    output: str | Path,
    locale_root: str | Path,
    project_uuid: str | None = None,
    allowed_content_paths: Iterable[str | Path] = (),
    allowed_text: Iterable[str] = (),
) -> dict[str, Any]:
    """Capture public and authenticated pages from a locale-enabled DSW stack."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise LocaleToolError(
            "Browser preview requires: pip install 'dsw-locale-tool[preview]'"
        ) from error

    api = DswApi(api_url)
    api.wait_until_operational(client_url)
    token = api.login(email, password)
    user = api.current_user()
    api.complete_tours()
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    base_url = client_url.rstrip("/")
    expires_at = (datetime.now(UTC) + timedelta(days=14)).isoformat().replace("+00:00", "Z")
    session = {
        "apiUrl": api_url.rstrip("/"),
        "fullscreen": False,
        "sidebarCollapsed": False,
        "rightPanelCollapsed": True,
        "token": {"token": token, "expiresAt": expires_at},
        "v9": True,
    }
    routes = _authenticated_routes(project_uuid)
    scenarios = _interactive_scenarios(project_uuid)

    report: dict[str, Any] = {"schema_version": 1, "clientUrl": base_url, "screenshots": []}
    observations: list[dict[str, str]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()

        public_context = browser.new_context(viewport={"width": 1440, "height": 1000})
        public_page = public_context.new_page()
        public_page.goto(f"{base_url}/login", wait_until="domcontentloaded", timeout=60_000)
        _wait_for_application(public_page)
        _wait_for_page_available(public_page, "login")
        _capture_page(
            public_page,
            name="login",
            output_path=output_path,
            report=report,
            observations=observations,
            full_page=True,
        )
        public_context.close()

        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        session_json = json.dumps(json.dumps(session, ensure_ascii=False))
        page.add_init_script(f"window.localStorage.setItem('session/wizard', {session_json});")
        for name, route in routes.items():
            page.goto(f"{base_url}{route}", wait_until="domcontentloaded", timeout=60_000)
            _wait_for_application(page)
            _wait_for_page_available(page, name)
            _capture_page(
                page,
                name=name,
                output_path=output_path,
                report=report,
                observations=observations,
                full_page=True,
            )
        context.close()

        for scenario in scenarios:
            scenario_context = browser.new_context(viewport={"width": 1440, "height": 1000})
            scenario_page = scenario_context.new_page()
            scenario_page.add_init_script(
                f"window.localStorage.setItem('session/wizard', {session_json});"
            )
            _capture_interactive_scenario(
                scenario_page,
                base_url=base_url,
                scenario=scenario,
                output_path=output_path,
                report=report,
                observations=observations,
            )
            scenario_context.close()
        browser.close()

    allowed = load_allowed_content(
        allowed_content_paths,
        set(allowed_text) | _user_content(user),
    )
    runtime_report = classify_runtime_observations(
        observations,
        locale_root=locale_root,
        allowed_content=allowed,
    )
    runtime_json, runtime_markdown = write_runtime_report(runtime_report, output_path)
    report["runtime"] = {
        "counts": runtime_report["counts"],
        "json": runtime_json.name,
        "markdown": runtime_markdown.name,
    }

    (output_path / "preview.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report
