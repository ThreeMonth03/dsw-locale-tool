"""Command-line interface for DSW locale maintenance."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from pydantic import ValidationError

from dsw_locale_tool.audit import audit_repository, failing_categories, write_reports
from dsw_locale_tool.build import build_source, package_source
from dsw_locale_tool.changes import validate_translation_pr
from dsw_locale_tool.config import load_config
from dsw_locale_tool.dsw import DswApi
from dsw_locale_tool.errors import LocaleToolError
from dsw_locale_tool.preview import capture_preview, generate_preview_config
from dsw_locale_tool.reconcile import reconcile_version_config, write_reconcile_report
from dsw_locale_tool.sync import fetch_upstream_branch_heads, sync_upstream
from dsw_locale_tool.versions import (
    available_git_branches,
    build_version_report,
    fetch_weblate_versions,
    write_version_report,
)


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

    validate_pr_parser = subparsers.add_parser(
        "validate-pr", help="Validate files changed by a translation pull request"
    )
    validate_pr_parser.add_argument("--base-root", type=Path, required=True)
    validate_pr_parser.add_argument("--head-root", type=Path, required=True)
    validate_pr_parser.add_argument("--branch", required=True)

    versions_parser = subparsers.add_parser(
        "version-report", help="Compare configured versions and branches with official Weblate"
    )
    versions_parser.add_argument("--config", type=Path, required=True)
    versions_parser.add_argument(
        "--repository-root",
        type=Path,
        help="Translation checkout used to verify sync/vX.Y branches",
    )
    versions_parser.add_argument("--report-dir", type=Path, default=Path("reports/versions"))
    versions_parser.add_argument("--fail-on-drift", action="store_true")

    reconcile_parser = subparsers.add_parser(
        "reconcile-versions",
        help="Add ready Weblate versions and update configured lifecycle states",
    )
    reconcile_parser.add_argument("--config", type=Path, required=True)
    reconcile_parser.add_argument("--report-dir", type=Path, default=Path("reports/maintenance"))

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

    preview_config_parser = subparsers.add_parser(
        "preview-config", help="Generate ephemeral secrets and DSW preview configuration"
    )
    preview_config_parser.add_argument("--output", type=Path, required=True)
    preview_config_parser.add_argument(
        "--client-url",
        default=os.getenv("DSW_CLIENT_URL", "http://localhost:8080/wizard"),
    )

    install_parser = subparsers.add_parser(
        "install-dsw", help="Import and enable a locale bundle in a running DSW"
    )
    install_parser.add_argument("--bundle", type=Path, required=True)
    install_parser.add_argument("--api-url", default=os.getenv("DSW_API_URL"))
    install_parser.add_argument("--api-key", default=os.getenv("DSW_API_KEY"))
    install_parser.add_argument(
        "--api-key-file",
        type=Path,
        default=Path(value) if (value := os.getenv("DSW_API_KEY_FILE")) else None,
    )
    install_parser.add_argument(
        "--email", default=os.getenv("DSW_ADMIN_EMAIL", "albert.einstein@example.com")
    )
    install_parser.add_argument("--password", default=os.getenv("DSW_ADMIN_PASSWORD"))
    install_parser.add_argument("--default-locale", action="store_true")
    install_parser.add_argument("--wait-timeout", type=float, default=300)

    seed_parser = subparsers.add_parser(
        "seed-project", help="Import a Knowledge Model and create a preview project"
    )
    seed_parser.add_argument("--knowledge-model", type=Path, required=True)
    seed_parser.add_argument("--project-name", default="Locale Preview")
    seed_parser.add_argument("--api-url", default=os.getenv("DSW_API_URL"))
    seed_parser.add_argument(
        "--email", default=os.getenv("DSW_ADMIN_EMAIL", "albert.einstein@example.com")
    )
    seed_parser.add_argument("--password", default=os.getenv("DSW_ADMIN_PASSWORD"))

    capture_parser = subparsers.add_parser(
        "capture-preview", help="Capture translated DSW pages with Playwright"
    )
    capture_parser.add_argument(
        "--client-url",
        default=os.getenv("DSW_CLIENT_URL", "http://localhost:8080/wizard"),
    )
    capture_parser.add_argument("--api-url", default=os.getenv("DSW_API_URL"))
    capture_parser.add_argument(
        "--email", default=os.getenv("DSW_ADMIN_EMAIL", "albert.einstein@example.com")
    )
    capture_parser.add_argument("--password", default=os.getenv("DSW_ADMIN_PASSWORD"))
    capture_parser.add_argument("--output", type=Path, required=True)
    capture_parser.add_argument("--project-uuid")
    return parser


def _required(value: str | None, environment_name: str) -> str:
    if not value:
        raise LocaleToolError(f"Missing required option or {environment_name} environment variable")
    return value


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

    if arguments.command == "validate-pr":
        print(
            json.dumps(
                validate_translation_pr(
                    arguments.base_root,
                    arguments.head_root,
                    arguments.branch,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if arguments.command == "version-report":
        config = load_config(arguments.config)
        branch_refs = (
            available_git_branches(arguments.repository_root) if arguments.repository_root else None
        )
        report = build_version_report(
            config,
            fetch_weblate_versions(config),
            branch_refs=branch_refs,
        )
        json_path, markdown_path = write_version_report(report, arguments.report_dir)
        print(f"Wrote {json_path} and {markdown_path}")
        if arguments.fail_on_drift and not report["aligned"]:
            print("Version alignment drift detected", file=sys.stderr)
            return 2
        return 0

    if arguments.command == "reconcile-versions":
        config = load_config(arguments.config)
        report = reconcile_version_config(
            arguments.config,
            fetch_weblate_versions(config),
            fetch_upstream_branch_heads(config.upstream.repository),
        )
        json_path, markdown_path = write_reconcile_report(report, arguments.report_dir)
        print(f"Wrote {json_path} and {markdown_path}")
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

    if arguments.command == "preview-config":
        print(generate_preview_config(arguments.output, client_url=arguments.client_url))
        return 0

    if arguments.command == "install-dsw":
        api = DswApi(_required(arguments.api_url, "DSW_API_URL"))
        api.wait_until_ready(wait_timeout=arguments.wait_timeout)
        api_key = arguments.api_key
        if not api_key and arguments.api_key_file:
            try:
                api_key = arguments.api_key_file.read_text(encoding="utf-8")
            except OSError as error:
                raise LocaleToolError(
                    f"Unable to read DSW API key file {arguments.api_key_file}: {error}"
                ) from error
        if api_key:
            api.use_api_key(api_key)
        else:
            api.login(
                _required(arguments.email, "DSW_ADMIN_EMAIL"),
                _required(arguments.password, "DSW_ADMIN_PASSWORD"),
            )
        result = api.install_locale(arguments.bundle, default_locale=arguments.default_locale)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if arguments.command == "seed-project":
        api = DswApi(_required(arguments.api_url, "DSW_API_URL"))
        api.login(
            _required(arguments.email, "DSW_ADMIN_EMAIL"),
            _required(arguments.password, "DSW_ADMIN_PASSWORD"),
        )
        print(
            api.seed_project(
                arguments.knowledge_model,
                project_name=arguments.project_name,
            )
        )
        return 0

    if arguments.command == "capture-preview":
        result = capture_preview(
            client_url=arguments.client_url,
            api_url=_required(arguments.api_url, "DSW_API_URL"),
            email=_required(arguments.email, "DSW_ADMIN_EMAIL"),
            password=_required(arguments.password, "DSW_ADMIN_PASSWORD"),
            output=arguments.output,
            project_uuid=arguments.project_uuid,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
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
