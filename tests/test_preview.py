"""Ephemeral preview configuration tests."""

from __future__ import annotations

from types import SimpleNamespace

import yaml

from dsw_locale_tool.preview import generate_preview_config


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
