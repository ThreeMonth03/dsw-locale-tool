"""Production Compose fragment tests."""

from __future__ import annotations

from pathlib import Path

import yaml


def test_production_fragment_requires_image_and_is_hardened():
    path = Path(__file__).parents[1] / "production" / "compose.locale.yml"
    compose = yaml.safe_load(path.read_text(encoding="utf-8"))
    service = compose["services"]["locale-installer"]

    assert service["image"] == (
        "${DSW_LOCALE_INSTALLER_IMAGE:?Set DSW_LOCALE_INSTALLER_IMAGE "
        "to an immutable locale installer image}"
    )
    assert service["platform"] == "linux/amd64"
    assert service["depends_on"] == {"server": {"condition": "service_started"}}
    assert service["network_mode"] == "service:server"
    assert "networks" not in service
    assert service["environment"] == {
        "DSW_API_URL": "http://localhost:3000/wizard-api",
        "DSW_API_KEY_FILE": "/run/secrets/dsw_locale_api_key",
    }
    assert "DSW_ADMIN_PASSWORD" not in service["environment"]
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert service["security_opt"] == ["no-new-privileges:true"]
    assert compose["secrets"]["dsw_locale_api_key"]["file"] == ("./secrets/dsw_locale_api_key")


def test_client_fragment_requires_an_immutable_image():
    path = Path(__file__).parents[1] / "production" / "compose.client.yml"
    compose = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert compose == {
        "services": {
            "client": {
                "image": (
                    "${DSW_CLIENT_IMAGE:?Set DSW_CLIENT_IMAGE to an immutable "
                    "localizable client image}"
                )
            }
        }
    }
