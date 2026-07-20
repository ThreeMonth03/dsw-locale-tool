"""Immutable preview content download tests."""

from __future__ import annotations

import hashlib

import pytest

from dsw_locale_tool.config import TranslationConfig
from dsw_locale_tool.errors import LocaleToolError
from dsw_locale_tool.preview_content import fetch_preview_content
from tests.conftest import make_config


def configured_preview() -> tuple[TranslationConfig, dict[str, bytes]]:
    """Build a config and deterministic remote artifact payloads."""

    artifacts = {
        "https://example.test/root.km": b'{"id":"dsw:root-zh-hant:2.7.0"}\n',
        "https://example.test/template.zip": b"document-template",
    }
    data = make_config().model_dump(mode="json")
    data["versions"]["v4.32"]["preview"] = {
        "knowledge_model": {
            "url": "https://example.test/root.km",
            "sha256": hashlib.sha256(artifacts["https://example.test/root.km"]).hexdigest(),
        },
        "document_template": {
            "url": "https://example.test/template.zip",
            "sha256": hashlib.sha256(artifacts["https://example.test/template.zip"]).hexdigest(),
        },
        "document_format_uuid": "a9293d08-59a4-4e6b-ae62-7a6a570b031c",
    }
    return TranslationConfig.model_validate(data), artifacts


def test_fetch_preview_content_downloads_hashes_and_writes_both_assets(tmp_path):
    config, artifacts = configured_preview()

    result = fetch_preview_content(
        config,
        "v4.32",
        tmp_path,
        downloader=artifacts.__getitem__,
    )

    assert (tmp_path / "knowledge-model.km").read_bytes() == artifacts[
        "https://example.test/root.km"
    ]
    assert (tmp_path / "document-template.zip").read_bytes() == artifacts[
        "https://example.test/template.zip"
    ]
    assert result["document_format_uuid"] == "a9293d08-59a4-4e6b-ae62-7a6a570b031c"


def test_fetch_preview_content_rejects_checksum_mismatch(tmp_path):
    config, artifacts = configured_preview()
    artifacts["https://example.test/root.km"] = b"tampered"

    with pytest.raises(LocaleToolError, match="checksum mismatch"):
        fetch_preview_content(
            config,
            "v4.32",
            tmp_path,
            downloader=artifacts.__getitem__,
        )


def test_fetch_preview_content_requires_version_configuration(tmp_path):
    with pytest.raises(LocaleToolError, match="No preview content"):
        fetch_preview_content(make_config(), "v4.32", tmp_path)
