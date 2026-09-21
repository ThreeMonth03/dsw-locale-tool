"""Offline regression tests for bounded, fuzzy-only submissions."""

from __future__ import annotations

import copy
from dataclasses import replace

import pytest

from dsw_locale_tool.catalog import load_catalog
from dsw_locale_tool.errors import LocaleToolError
from dsw_locale_tool.submission import apply_submission, prepare_submission, write_submission
from dsw_locale_tool.translation_tree import load_translation_tree, write_translation_tree
from tests.conftest import make_translation_tree


class FakeClient:
    project = "dsw-4-32"
    token = "test-only"

    def __init__(self, root):
        self.catalogs = {c: load_catalog(root / "upstream" / f"{c}.po") for c in ("wizard", "mail")}
        self.calls = []
        self.records = {}
        self.before_write = None
        for component, po in self.catalogs.items():
            for e in po:
                number = len(self.records) + 1
                source = [e.msgid] + ([e.msgid_plural] if e.msgid_plural else [])
                target = list(e.msgstr_plural.values()) if e.msgid_plural else [e.msgstr]
                self.records[number] = {
                    "id": number,
                    "component": component,
                    "source": source,
                    "context": e.msgctxt or "",
                    "target": target,
                    "last_updated": "original",
                    "state": 10 if "fuzzy" in e.flags else (20 if any(target) else 0),
                }

    def catalog(self, component):
        return copy.deepcopy(self.catalogs[component])

    def units(self, component):
        return [copy.deepcopy(u) for u in self.records.values() if u["component"] == component]

    def get_unit(self, number, component):
        if self.before_write:
            self.before_write(self.records[number])
        return copy.deepcopy(self.records[number])

    def set_fuzzy(self, number, text):
        self.calls.append((number, text))
        unit = self.records[number]
        unit.update(target=[text], state=10)
        e = self.catalogs[unit["component"]].find(
            unit["source"][0], msgctxt=unit["context"] or None
        )
        e.msgstr = text
        e.flags = ["fuzzy"]


def setup(root):
    make_translation_tree(root)
    units = load_translation_tree(root)
    for key, unit in units.items():
        units[key] = replace(unit, translation="數量：%s" if "%s" in unit.msgid else "尚未填寫")
    write_translation_tree(root, units)
    return FakeClient(root)


def test_prepare_is_read_only_and_exports_only_candidates(tmp_path):
    client = setup(tmp_path)
    before = client.catalog("wizard").__unicode__()
    report, catalogs = prepare_submission(tmp_path, client, limit=1)
    assert len(report["candidates"]) == 1
    assert report["skipped"][0]["reason"] == "batch limit"
    write_submission(report, catalogs, tmp_path / "reports")
    delta = load_catalog(tmp_path / "reports/wizard.po")
    assert len(delta) == 1
    assert delta[0].flags == ["fuzzy"]
    assert client.catalog("wizard").__unicode__() == before
    assert not client.calls


@pytest.mark.parametrize("flags", [[], ["fuzzy"]])
def test_nonempty_targets_protected_even_when_fuzzy(tmp_path, flags):
    client = setup(tmp_path)
    e = client.catalogs["wizard"].find("Count: %s")
    e.msgstr, e.flags = "同事翻譯 %s", flags
    report, _ = prepare_submission(tmp_path, client)
    assert len(report["candidates"]) == 1
    assert report["skipped"][0]["reason"] == "nonempty official translation protected"


def test_matching_fuzzy_translation_is_not_reapproved(tmp_path):
    client = setup(tmp_path)
    e = client.catalogs["wizard"].find("Count: %s")
    e.msgstr, e.flags = "數量：%s", ["fuzzy"]
    report, _ = prepare_submission(tmp_path, client)
    assert len(report["candidates"]) == 1
    assert report["skipped"][0]["reason"].startswith("already matches")
    assert e.flags == ["fuzzy"]


def test_explicit_correction_can_be_prepared(tmp_path):
    client = setup(tmp_path)
    client.catalogs["wizard"].find("Count: %s").msgstr = "先前譯文 %s"
    report, _ = prepare_submission(tmp_path, client, allow_corrections=True)
    assert len(report["candidates"]) == 2


@pytest.mark.parametrize(
    "field,value", [("msgctxt", "another-context"), ("msgid_plural", "new plural")]
)
def test_context_and_plural_must_match_live_source(tmp_path, field, value):
    client = setup(tmp_path)
    setattr(client.catalogs["wizard"].find("Count: %s"), field, value)
    report, _ = prepare_submission(tmp_path, client)
    assert len(report["candidates"]) == 1
    assert report["skipped"][0]["reason"] == "source absent from live Weblate"


def test_apply_marks_fuzzy_and_verifies_whole_catalog(tmp_path):
    client = setup(tmp_path)
    report, catalogs = prepare_submission(tmp_path, client)
    apply_submission(report, catalogs, client, tmp_path / "reports", settle_seconds=0)
    assert report["verified"]
    assert len(client.calls) == 2
    assert not report["outside_changes"]
    assert load_catalog(tmp_path / "reports/after-wizard.po").find("Hello").msgstr == "您好"


@pytest.mark.parametrize("change", ["wording", "timestamp", "source", "readonly"])
def test_concurrent_change_stops_before_write(tmp_path, change):
    client = setup(tmp_path)
    report, catalogs = prepare_submission(tmp_path, client)

    def edit(unit):
        if change == "wording":
            unit["target"] = ["同事剛翻譯"]
        elif change == "timestamp":
            unit["last_updated"] = "later"
        elif change == "source":
            unit["source"] = ["Changed source"]
        else:
            unit["state"] = 100

    client.before_write = edit
    with pytest.raises(LocaleToolError, match="changed since preflight"):
        apply_submission(report, catalogs, client, tmp_path / "reports", settle_seconds=0)
    assert not client.calls
    assert (tmp_path / "reports/submission.json").is_file()


def test_rewrite_is_reported_not_rolled_back(tmp_path):
    client = setup(tmp_path)
    report, catalogs = prepare_submission(tmp_path, client)
    original = client.set_fuzzy

    def rewrite(number, text):
        original(number, text)
        client.records[number]["target"] = ["自動翻譯"]

    client.set_fuzzy = rewrite
    with pytest.raises(LocaleToolError, match="did not retain"):
        apply_submission(report, catalogs, client, tmp_path / "reports", settle_seconds=0)
    assert len(client.calls) == 1
    assert client.records[client.calls[0][0]]["target"] == ["自動翻譯"]
    assert report["attempted_ids"]


def test_unrelated_live_change_is_reported_without_writes_to_it(tmp_path):
    client = setup(tmp_path)
    report, catalogs = prepare_submission(tmp_path, client)
    client.catalogs["wizard"].find("Hello").msgstr = "同事剛更新"
    with pytest.raises(LocaleToolError, match="Out-of-scope"):
        apply_submission(report, catalogs, client, tmp_path / "reports", settle_seconds=0)
    assert client.catalogs["wizard"].find("Hello").msgstr == "同事剛更新"
    assert len(client.calls) == 2


def test_write_failure_not_retried_and_keeps_report(tmp_path):
    client = setup(tmp_path)
    report, catalogs = prepare_submission(tmp_path, client)

    def failure(number, text):
        client.calls.append((number, text))
        raise LocaleToolError("Weblate PATCH failed (500)")

    client.set_fuzzy = failure
    with pytest.raises(LocaleToolError, match="500"):
        apply_submission(report, catalogs, client, tmp_path / "reports", settle_seconds=0)
    assert len(client.calls) == 1
    assert report["attempted_ids"] == [client.calls[0][0]]


@pytest.mark.parametrize("limit", [0, -1, 201])
def test_invalid_batch_limit_is_rejected(tmp_path, limit):
    client = setup(tmp_path)
    with pytest.raises(LocaleToolError, match="Batch limit"):
        prepare_submission(tmp_path, client, limit=limit)


def test_plan_hash_covers_live_values_and_candidate_limit(tmp_path):
    client = setup(tmp_path)
    original, _ = prepare_submission(tmp_path, client, allow_corrections=True)
    repeated, _ = prepare_submission(tmp_path, client, allow_corrections=True)
    limited, _ = prepare_submission(tmp_path, client, limit=1)
    assert original["plan_sha256"] == repeated["plan_sha256"]
    assert original["plan_sha256"] != limited["plan_sha256"]
    client.catalogs["wizard"].find("Count: %s").msgstr = "新基準 %s"
    changed, _ = prepare_submission(tmp_path, client, allow_corrections=True)
    assert original["plan_sha256"] != changed["plan_sha256"]
