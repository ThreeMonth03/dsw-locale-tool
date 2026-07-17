"""Production Compose fragment tests."""

from __future__ import annotations

from pathlib import Path

import yaml


def test_production_fragment_is_key_only_and_hardened():
    path = Path(__file__).parents[1] / "production" / "compose.locale.yml"
    compose = yaml.safe_load(path.read_text(encoding="utf-8"))
    service = compose["services"]["locale-installer"]

    assert service["image"] == "ghcr.io/threemonth03/dsw-locale-installer:4.32.2"
    assert service["platform"] == "linux/amd64"
    assert service["depends_on"] == {"server": {"condition": "service_started"}}
    assert service["environment"] == {
        "DSW_API_URL": "http://server:3000/wizard-api",
        "DSW_API_KEY_FILE": "/run/secrets/dsw_locale_api_key",
    }
    assert "DSW_ADMIN_PASSWORD" not in service["environment"]
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert service["security_opt"] == ["no-new-privileges:true"]
    assert compose["secrets"]["dsw_locale_api_key"]["file"] == ("./secrets/dsw_locale_api_key")
