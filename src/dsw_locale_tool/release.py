"""Immutable locale release version management."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from dsw_locale_tool.config import load_config
from dsw_locale_tool.errors import LocaleToolError

STABLE_VERSION_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$"
)
VERSION_HEADING_PATTERN = re.compile(r"^  v\d+\.\d+:\s*$")


def bump_locale_version(config_path: str | Path, version_key: str) -> dict[str, Any]:
    """Increase one stable locale patch version without rewriting unrelated YAML."""
    path = Path(config_path)
    config = load_config(path)
    current = config.version(version_key).locale_version
    match = STABLE_VERSION_PATTERN.fullmatch(current)
    if match is None:
        raise LocaleToolError(
            f"Automated release bumps require a stable X.Y.Z locale version: {current!r}"
        )

    expected_minor = version_key.removeprefix("v")
    actual_minor = f"{match.group('major')}.{match.group('minor')}"
    if actual_minor != expected_minor:
        raise LocaleToolError(
            f"{version_key}.locale_version must start with {expected_minor!r}: {current!r}"
        )
    next_version = f"{actual_minor}.{int(match.group('patch')) + 1}"

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    heading = f"  {version_key}:"
    starts = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == heading]
    if len(starts) != 1:
        raise LocaleToolError(f"Expected exactly one configuration section for {version_key}")
    start = starts[0] + 1
    end = next(
        (
            index
            for index in range(start, len(lines))
            if VERSION_HEADING_PATTERN.fullmatch(lines[index].rstrip("\r\n"))
        ),
        len(lines),
    )
    prefix = "    locale_version: "
    candidates = [index for index in range(start, end) if lines[index].startswith(prefix)]
    if len(candidates) != 1:
        raise LocaleToolError(
            f"Expected exactly one locale_version field in the {version_key} section"
        )
    index = candidates[0]
    if lines[index].rstrip("\r\n") != f"{prefix}{current}":
        raise LocaleToolError(
            f"Expected canonical locale_version formatting in the {version_key} section"
        )
    newline = (
        "\r\n" if lines[index].endswith("\r\n") else "\n" if lines[index].endswith("\n") else ""
    )
    lines[index] = f"{prefix}{next_version}{newline}"
    path.write_text("".join(lines), encoding="utf-8")
    load_config(path)

    return {
        "version": version_key,
        "previous_locale_version": current,
        "locale_version": next_version,
    }
