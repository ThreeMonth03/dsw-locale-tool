"""Commands for translation checks, official synchronization, and controlled uploads."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from pydantic import ValidationError

from dsw_locale_tool.audit import audit_repository, failing_categories, write_reports
from dsw_locale_tool.changes import validate_translation_pr
from dsw_locale_tool.config import load_config
from dsw_locale_tool.errors import LocaleToolError
from dsw_locale_tool.reconcile import reconcile_version_config, write_reconcile_report
from dsw_locale_tool.submission import apply_submission, prepare_submission, write_submission
from dsw_locale_tool.sync import fetch_upstream_branch_heads, sync_upstream, validate_upstream_lock
from dsw_locale_tool.translation_tree import refresh_translation_tree
from dsw_locale_tool.versions import fetch_weblate_versions
from dsw_locale_tool.weblate import WeblateClient


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("check", "refresh-tree"):
        command = commands.add_parser(name)
        command.add_argument("--root", type=Path, default=Path("."))
        if name == "check":
            command.add_argument("--report-dir", type=Path, default=Path("reports"))
    command = commands.add_parser("validate-pr")
    command.add_argument("--base-root", type=Path, required=True)
    command.add_argument("--head-root", type=Path, required=True)
    command.add_argument("--branch", required=True)
    command.add_argument("--report-dir", type=Path, default=Path("reports"))
    for name in ("validate-config", "sync-upstream", "reconcile-versions", "submit"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path, required=True)
        if name == "reconcile-versions":
            command.add_argument("--report-dir", type=Path, default=Path("reports"))
        elif name != "validate-config":
            command.add_argument("--version", required=True)
            command.add_argument("--root", type=Path, default=Path("."))
        if name == "submit":
            command.add_argument("--report-dir", type=Path, default=Path("reports/submission"))
            command.add_argument("--limit", type=int, default=20)
            command.add_argument("--allow-corrections", action="store_true")
            command.add_argument("--apply", action="store_true")
            command.add_argument("--expected-plan", default="")
    return result


def check(root: Path, output: Path) -> dict:
    report = audit_repository(root)
    write_reports(report, output)
    failures = failing_categories(report, {"structure", "placeholders"})
    if failures:
        raise LocaleToolError("Local translation checks failed: " + ", ".join(failures))
    return report


def run(args) -> dict:
    if args.command == "check":
        return check(args.root, args.report_dir)
    if args.command == "refresh-tree":
        return refresh_translation_tree(args.root)
    if args.command == "validate-pr":
        report = validate_translation_pr(args.base_root, args.head_root, args.branch)
        check(args.head_root, args.report_dir)
        (args.report_dir / "pr.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        return report
    config = load_config(args.config)
    if args.command == "validate-config":
        return {"valid": True, "versions": list(config.versions)}
    if args.command == "reconcile-versions":
        report = reconcile_version_config(
            args.config,
            fetch_weblate_versions(config),
            fetch_upstream_branch_heads(config.upstream.repository),
        )
        write_reconcile_report(report, args.report_dir)
        return report
    config.version(args.version)
    if args.command == "sync-upstream":
        return sync_upstream(config, args.version, args.root)
    validate_upstream_lock(config, args.version, args.root)
    if args.apply and not os.environ.get("LOCALIZE_API_TOKEN"):
        raise LocaleToolError("Set LOCALIZE_API_TOKEN before applying; dry runs do not need it")
    client = WeblateClient(args.version, os.environ.get("LOCALIZE_API_TOKEN"))
    report, catalogs = prepare_submission(
        args.root, client, limit=args.limit, allow_corrections=args.allow_corrections
    )
    write_submission(report, catalogs, args.report_dir)
    if args.apply:
        if args.expected_plan != report["plan_sha256"]:
            raise LocaleToolError(
                "Apply requires --expected-plan from an unchanged reviewed dry run"
            )
        apply_submission(report, catalogs, client, args.report_dir)
    return {
        "project": report["project"],
        "candidates": len(report["candidates"]),
        "skipped": len(report["skipped"]),
        "apply": args.apply,
        "plan_sha256": report["plan_sha256"],
        "verified": report.get("verified", False),
    }


def main() -> int:
    args = parser().parse_args()
    try:
        report = run(args)
    except (LocaleToolError, ValidationError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
