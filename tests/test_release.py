"""Immutable locale release version tests."""

from __future__ import annotations

import pytest
import yaml

from dsw_locale_tool.errors import LocaleToolError
from dsw_locale_tool.release import bump_locale_version
from tests.conftest import make_config


def _write_config(path, locale_version="4.32.7"):
    data = make_config().model_dump(mode="json")
    data["versions"]["v4.32"]["locale_version"] = locale_version
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_bumps_only_target_locale_patch_version(tmp_path):
    path = tmp_path / "translation-config.yml"
    _write_config(path)
    before = path.read_text(encoding="utf-8")

    report = bump_locale_version(path, "v4.32")

    after = path.read_text(encoding="utf-8")
    assert report == {
        "version": "v4.32",
        "previous_locale_version": "4.32.7",
        "locale_version": "4.32.8",
    }
    assert after == before.replace("locale_version: 4.32.7", "locale_version: 4.32.8")


def test_rejects_prerelease_version(tmp_path):
    path = tmp_path / "translation-config.yml"
    _write_config(path, "4.32.7-rc.1")

    with pytest.raises(LocaleToolError, match="stable X.Y.Z"):
        bump_locale_version(path, "v4.32")
