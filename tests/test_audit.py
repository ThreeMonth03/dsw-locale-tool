"""Keep official diagnostics separate from contribution failures."""

from dataclasses import replace

from dsw_locale_tool.audit import audit_repository, failing_categories, write_reports
from dsw_locale_tool.catalog import load_catalog
from dsw_locale_tool.translation_tree import load_translation_tree, write_translation_tree
from tests.conftest import make_translation_tree


def test_local_placeholder_loss_fails(tmp_path):
    make_translation_tree(tmp_path)
    report = audit_repository(tmp_path)
    assert failing_categories(report, {"placeholders", "structure"}) == ["placeholders"]
    assert report["components"]["wizard"]["counts"]["empty"] == 2


def test_official_placeholder_error_is_reported_not_blocking(tmp_path):
    make_translation_tree(tmp_path)
    units = load_translation_tree(tmp_path)
    key = ("wizard", None, "Count: %s")
    units[key] = replace(units[key], translation="數量：%s")
    write_translation_tree(tmp_path, units)
    path = tmp_path / "upstream/wizard.po"
    po = load_catalog(path)
    po.find("Count: %s").msgstr = "舊譯文缺參數"
    po.save(path)
    report = audit_repository(tmp_path)
    assert not failing_categories(report, {"placeholders", "structure"})
    assert report["components"]["wizard"]["upstream_placeholder_issues"]
    write_reports(report, tmp_path / "reports")


def test_fuzzy_is_not_counted_as_empty(tmp_path):
    make_translation_tree(tmp_path)
    path = tmp_path / "upstream/wizard.po"
    po = load_catalog(path)
    po.find("Still missing").msgstr = "既有譯文"
    po.find("Still missing").flags = ["fuzzy"]
    po.save(path)
    counts = audit_repository(tmp_path)["components"]["wizard"]["counts"]
    assert counts["empty"] == 1
    assert counts["fuzzy"] == 1
