"""Configuration validation tests."""

from __future__ import annotations

import yaml
from pydantic import ValidationError

from dsw_locale_tool.config import TranslationConfig, load_config
from tests.conftest import make_config


def test_load_config_round_trip(tmp_path):
    config = make_config()
    path = tmp_path / "translation-config.yml"
    path.write_text(
        yaml.safe_dump(config.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    loaded = load_config(path)

    assert loaded.locale.locale_id == "zh_Hant"
    assert loaded.version("v4.32").upstream_ref == "v4.32"


def test_config_rejects_app_version_from_another_minor():
    data = make_config().model_dump(mode="json")
    data["versions"]["v4.32"]["recommended_app_version"] = "4.31.9"

    try:
        TranslationConfig.model_validate(data)
    except ValidationError as error:
        assert "must start with '4.32.'" in str(error)
    else:
        raise AssertionError("Configuration should have been rejected")


def test_config_rejects_locale_version_from_another_minor():
    data = make_config().model_dump(mode="json")
    data["versions"]["v4.32"]["locale_version"] = "4.31.9"

    try:
        TranslationConfig.model_validate(data)
    except ValidationError as error:
        assert "v4.32.locale_version must start with '4.32.'" in str(error)
    else:
        raise AssertionError("Configuration should have been rejected")


def test_config_rejects_unknown_fields():
    data = make_config().model_dump(mode="json")
    data["upstream"]["typo"] = True

    try:
        TranslationConfig.model_validate(data)
    except ValidationError as error:
        assert "Extra inputs are not permitted" in str(error)
    else:
        raise AssertionError("Configuration should have been rejected")
