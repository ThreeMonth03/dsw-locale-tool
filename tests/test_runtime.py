"""Runtime English observation classification tests."""

from __future__ import annotations

import json

from dsw_locale_tool.runtime import (
    classify_runtime_observations,
    is_english_candidate,
    load_allowed_content,
    render_runtime_markdown,
)
from tests.conftest import make_translation_tree


def _observation(text: str, *, route: str = "dashboard", selector: str = "#target"):
    return {
        "route": route,
        "url": f"http://localhost/{route}",
        "text": text,
        "kind": "text",
        "selector": selector,
    }


def test_english_candidate_rejects_chinese_identifiers_and_urls():
    assert is_english_candidate("Save changes") is True
    assert is_english_candidate("新增 OpenID 服務") is False
    assert is_english_candidate("https://example.test/path") is False
    assert is_english_candidate("4.32.0") is False
    assert is_english_candidate("zh-hant") is False
    assert is_english_candidate("depositar:zh_Hant:4.32.0") is False


def test_allowed_content_loads_all_json_string_values(tmp_path):
    content = tmp_path / "km.json"
    content.write_text(
        json.dumps({"name": "Basic KM", "chapters": [{"title": "Chapter One"}]}),
        encoding="utf-8",
    )

    allowed = load_allowed_content([content], ["Locale Preview"])

    assert {"Basic KM", "Chapter One", "Locale Preview", "DS Wizard"} <= allowed


def test_runtime_scan_distinguishes_catalog_and_runtime_findings(tmp_path):
    make_translation_tree(tmp_path)
    observations = [
        _observation("Still missing"),
        _observation("Hello"),
        _observation("Runtime only"),
        _observation("Button never extracted", route="projects"),
        _observation("I. Chapter One", route="questionnaire"),
        _observation("Button never extracted", route="projects", selector="#duplicate"),
    ]

    report = classify_runtime_observations(
        observations,
        locale_root=tmp_path,
        allowed_content={"Chapter One"},
    )

    assert report["counts"] == {
        "runtime_not_in_pot": 1,
        "official_missing": 1,
        "unexpected_source": 2,
        "allowed_content": 1,
    }
    runtime_finding = next(
        item for item in report["findings"] if item["category"] == "runtime_not_in_pot"
    )
    assert len(runtime_finding["locations"]) == 2
    markdown = render_runtime_markdown(report)
    assert "Button never extracted" in markdown
    assert "I. Chapter One" not in markdown
