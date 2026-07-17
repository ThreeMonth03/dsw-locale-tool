"""Execution plan tests."""

from __future__ import annotations

from dsw_locale_tool.config import TranslationConfig
from dsw_locale_tool.plans import build_maintained_matrix, build_release_info


def test_maintained_matrix_contains_live_versions_in_release_order():
    config = TranslationConfig.model_validate(
        {
            "schema_version": 1,
            "locale": {
                "organization_id": "depositar",
                "locale_id": "zh_Hant",
                "code": "zh-hant",
                "name": "繁體中文",
                "description": "測試語系",
                "license": "CC-BY-4.0",
            },
            "upstream": {
                "repository": "https://example.test/wizard-locales.git",
                "locale": "zh_Hant",
            },
            "branches": {"control": "main", "version_prefix": "release/"},
            "versions": {
                "v4.32": {
                    "upstream_ref": "v4.32",
                    "locale_version": "4.32.0",
                    "recommended_app_version": "4.32.0",
                    "state": "active",
                },
                "v4.9": {
                    "upstream_ref": "v4.9",
                    "locale_version": "4.9.0",
                    "recommended_app_version": "4.9.0",
                    "state": "maintenance",
                },
                "v4.10": {
                    "upstream_ref": "v4.10",
                    "locale_version": "4.10.0",
                    "recommended_app_version": "4.10.0",
                    "state": "retired",
                },
            },
        }
    )

    assert build_maintained_matrix(config) == {
        "include": [
            {
                "config_version": "v4.9",
                "translation_ref": "release/v4.9",
                "dsw_image_tag": "4.9",
            },
            {
                "config_version": "v4.32",
                "translation_ref": "release/v4.32",
                "dsw_image_tag": "4.32",
            },
        ]
    }

    assert build_release_info(config, "v4.32") == {
        "config_version": "v4.32",
        "translation_ref": "release/v4.32",
        "locale_version": "4.32.0",
        "recommended_app_version": "4.32.0",
        "state": "active",
    }
