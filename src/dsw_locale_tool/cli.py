"""Command-line interface for DSW locale maintenance."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from dsw_locale_tool.audit import audit_repository, failing_categories, write_reports
from dsw_locale_tool.build import build_source, package_source
from dsw_locale_tool.config import load_config
from dsw_locale_tool.errors import LocaleToolError
from dsw_locale_tool.sync import sync_upstream


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="dsw-locale",
        description="Maintain local overlays on official DSW UI locales.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate-config", help="Validate translation-config.yml"
    )
    validate_parser.add_argument("config", type=Path)

    sync_parser = subparsers.add_parser(
        "sync-upstream", help="Refresh the immutable official locale baseline"
    )
    sync_parser.add_argument("--config", type=Path, required=True)
    sync_parser.add_argument("--version", required=True)
    sync_parser.add_argument("--output", type=Path, default=Path.cwd())

    audit_parser = subparsers.add_parser(
        "audit", help="Report missing translations and overlay maintenance work"
    )
    audit_parser.add_argument("--root", type=Path, default=Path.cwd())
    audit_parser.add_argument("--report-dir", type=Path, default=Path("reports"))
    audit_parser.add_argument(
        "--fail-on",
        action="append",
        choices=("missing", "placeholders", "structure"),
        default=[],
        help="Return a non-zero status when this finding category is present",
    )

    build_parser_ = subparsers.add_parser(
        "build-source", help="Merge locale layers into a packager-ready directory"
    )
    build_parser_.add_argument("--config", type=Path, required=True)
    build_parser_.add_argument("--version", required=True)
    build_parser_.add_argument("--root", type=Path, default=Path.cwd())
    build_parser_.add_argument("--output", type=Path, required=True)
    build_parser_.add_argument("--force", action="store_true")

    package_parser = subparsers.add_parser(
        "package", help="Create a ZIP with the official pinned DSW locale packager"
    )
    package_parser.add_argument("--source", type=Path, required=True)
    package_parser.add_argument("--output", type=Path, required=True)
    return parser


def run(arguments: argparse.Namespace) -> int:
    """Run a parsed CLI command."""
    if arguments.command == "validate-config":
        config = load_config(arguments.config)
        print(
            json.dumps(
                {
                    "valid": True,
                    "locale": config.locale.locale_id,
                    "versions": sorted(config.versions),
                },
                ensure_ascii=False,
            )
        )
        return 0

    if arguments.command == "sync-upstream":
        lock = sync_upstream(
            load_config(arguments.config),
            arguments.version,
            arguments.output,
        )
        print(json.dumps(lock, ensure_ascii=False, indent=2))
        return 0

    if arguments.command == "audit":
        report = audit_repository(arguments.root)
        json_path, markdown_path = write_reports(report, arguments.report_dir)
        print(f"Wrote {json_path} and {markdown_path}")
        failures = failing_categories(report, set(arguments.fail_on))
        if failures:
            print(f"Audit failed on: {', '.join(failures)}", file=sys.stderr)
            return 2
        return 0

    if arguments.command == "build-source":
        output = build_source(
            load_config(arguments.config),
            arguments.version,
            arguments.root,
            arguments.output,
            force=arguments.force,
        )
        print(output)
        return 0

    if arguments.command == "package":
        print(package_source(arguments.source, arguments.output))
        return 0

    raise LocaleToolError(f"Unsupported command: {arguments.command}")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point with concise, stable error handling."""
    try:
        return run(build_parser().parse_args(argv))
    except (LocaleToolError, ValidationError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
