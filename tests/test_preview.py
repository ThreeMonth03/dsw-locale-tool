"""Ephemeral preview configuration tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import yaml

from dsw_locale_tool.errors import LocaleToolError
from dsw_locale_tool.preview import _assert_page_available, generate_preview_config


class FakeLocator:
    def __init__(self, visible: bool):
        self.visible = visible

    def is_visible(self):
        return self.visible


class FakePage:
    url = "http://localhost:8080/wizard/locales"

    def __init__(self, visible_marker: str | None = None):
        self.visible_marker = visible_marker

    def locator(self, selector: str):
        return FakeLocator(self.visible_marker is not None and self.visible_marker in selector)


def test_generate_preview_config_creates_fresh_secret_and_rsa_key(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "dsw_locale_tool.preview.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout="-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----\n"
        ),
    )
    output = tmp_path / "runtime" / "application.yml"

    generate_preview_config(output, client_url="http://localhost:8080/wizard")

    config = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert config["general"]["clientUrl"] == "http://localhost:8080/wizard"
    assert len(config["general"]["secret"]) == 32
    assert config["general"]["rsaPrivateKey"].startswith("-----BEGIN RSA PRIVATE KEY-----")
    assert config["database"]["connectionString"].endswith("/engine-wizard")
    assert config["cloud"]["publicRegistrationEnabled"] is False


def test_assert_page_available_accepts_normal_page():
    _assert_page_available(FakePage(), "locales")


def test_assert_page_available_rejects_not_found_page():
    with pytest.raises(LocaleToolError, match="route was not found"):
        _assert_page_available(FakePage("not-found"), "locales")
