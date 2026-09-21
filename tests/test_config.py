"""Strict synchronization configuration tests."""

import pytest
import yaml
from pydantic import ValidationError

from dsw_locale_tool.config import TranslationConfig, load_config
from tests.conftest import make_config


def test_config_round_trip(tmp_path):
    path = tmp_path / "config.yml"
    path.write_text(yaml.safe_dump(make_config().model_dump(mode="json")), encoding="utf-8")
    assert load_config(path).upstream.locale == "zh_Hant"


@pytest.mark.parametrize("field", ["locale_version", "recommended_app_version", "preview", "typo"])
def test_removed_and_unknown_version_settings_are_rejected(field):
    data = make_config().model_dump(mode="json")
    data["versions"]["v4.32"][field] = "unused"
    with pytest.raises(ValidationError, match="Extra inputs"):
        TranslationConfig.model_validate(data)


def test_mismatched_version_and_source_branch_are_rejected():
    data = make_config().model_dump(mode="json")
    data["versions"]["v4.32"]["upstream_ref"] = "v4.31"
    with pytest.raises(ValidationError, match="must match"):
        TranslationConfig.model_validate(data)


@pytest.mark.parametrize("language", ["en", "fr", "zh_Hans"])
def test_other_language_cannot_be_submitted(language):
    data = make_config().model_dump(mode="json")
    data["upstream"]["locale"] = language
    with pytest.raises(ValidationError):
        TranslationConfig.model_validate(data)
