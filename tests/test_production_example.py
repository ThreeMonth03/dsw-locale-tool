"""Safety invariants for the copyable depositar production Compose override."""

from __future__ import annotations

from pathlib import Path

import yaml

EXAMPLE = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "depositar-production"
    / "docker-compose.locale.yml"
)


def test_locale_installer_compose_override_has_no_public_or_persistent_resources():
    compose = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    installer = compose["services"]["locale-installer"]

    assert installer["restart"] == "no"
    assert installer["profiles"] == ["locale-maintenance"]
    assert installer["platform"] == "linux/amd64"
    assert installer["networks"] == ["dsw_internal"]
    assert "ports" not in installer
    assert "volumes" not in installer


def test_locale_installer_uses_internal_server_and_secret_file():
    compose = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    installer = compose["services"]["locale-installer"]

    assert installer["environment"] == {
        "DSW_API_URL": "http://server:3000/wizard-api",
        "DSW_API_KEY_FILE": "/run/secrets/dsw_locale_api_key",
    }
    assert installer["secrets"] == ["dsw_locale_api_key"]
    assert "DSW_ADMIN_PASSWORD" not in installer["environment"]
    assert compose["secrets"]["dsw_locale_api_key"]["file"].startswith(
        "${DSW_LOCALE_API_KEY_SOURCE:-"
    )
