"""Locale audit tests."""

from __future__ import annotations

from dsw_locale_tool.audit import audit_repository, failing_categories, render_markdown
from tests.conftest import make_translation_tree


def test_audit_classifies_translation_work(tmp_path):
    make_translation_tree(tmp_path)

    report = audit_repository(tmp_path)
    wizard = report["components"]["wizard"]

    assert wizard["counts"] == {
        "source_messages": 3,
        "upstream_translated": 1,
        "effective_translated": 2,
        "missing": 1,
        "fuzzy": 0,
        "overrides": 2,
        "extras": 1,
        "extras_now_upstream": 0,
        "misplaced_overrides": 0,
        "redundant_overrides": 1,
        "placeholder_issues": 1,
    }
    assert wizard["missing"][0]["msgid"] == "Still missing"
    assert wizard["placeholder_issues"][0]["expected"] == {"%s": 1}


def test_audit_failure_policy_is_explicit(tmp_path):
    make_translation_tree(tmp_path)
    report = audit_repository(tmp_path)

    assert failing_categories(report, set()) == []
    assert failing_categories(report, {"missing", "placeholders"}) == [
        "missing",
        "placeholders",
    ]


def test_markdown_contains_summary_and_findings(tmp_path):
    make_translation_tree(tmp_path)

    markdown = render_markdown(audit_repository(tmp_path))

    assert "| wizard | 3 | 1 | 2 | 1 | 1 | 1 |" in markdown
    assert "`Still missing`" in markdown
