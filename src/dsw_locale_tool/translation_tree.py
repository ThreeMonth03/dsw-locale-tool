"""Human-editable Markdown translation units and generated gettext catalogs."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

import polib

from dsw_locale_tool.catalog import (
    catalog_index,
    entry_is_translated,
    entry_key,
    load_catalog,
    translated_strings,
)
from dsw_locale_tool.errors import LocaleToolError

COMPONENTS = ("wizard", "mail")
TRANSLATIONS_DIRECTORY = "translations"
UNIT_SUFFIX = ".translation.md"
UnitKind = Literal["message", "runtime"]
UnitKey: TypeAlias = tuple[str, str | None, str]

METADATA_PREFIX = "<!-- dsw-locale-unit: "
METADATA_SUFFIX = " -->"
SOURCE_HEADING = "## Source (en)"
PLURAL_HEADING = "## Source plural (en)"
TRANSLATION_HEADING = "## Translation (zh_Hant)"
INSTRUCTIONS = "Edit only the `Translation (zh_Hant)` block below."
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
FENCE_PATTERN = re.compile(r"^(?P<fence>~{3,})text$")
SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class TranslationUnit:
    """One source string and its local Traditional Chinese translation."""

    component: str
    kind: UnitKind
    msgid: str
    translation: str = ""
    msgctxt: str | None = None
    msgid_plural: str | None = None

    @property
    def key(self) -> UnitKey:
        """Return the gettext identity scoped to one DSW component."""
        return self.component, self.msgctxt, self.msgid


def _identity(unit: TranslationUnit) -> dict[str, str | None]:
    return {
        "component": unit.component,
        "kind": unit.kind,
        "msgctxt": unit.msgctxt,
        "msgid": unit.msgid,
        "msgid_plural": unit.msgid_plural,
    }


def source_hash(unit: TranslationUnit) -> str:
    """Hash the complete machine identity of a translation unit."""
    payload = json.dumps(
        _identity(unit),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _slug(value: str) -> str:
    candidate = SLUG_PATTERN.sub("-", value.casefold()).strip("-")[:48].rstrip("-")
    return candidate or "message"


def unit_relative_path(unit: TranslationUnit) -> Path:
    """Return the deterministic repository path for a unit."""
    filename = f"{_slug(unit.msgid)}--{source_hash(unit)[:12]}{UNIT_SUFFIX}"
    return Path(TRANSLATIONS_DIRECTORY) / unit.component / filename


def _fence_for(*values: str | None) -> str:
    longest = 0
    for value in values:
        if value:
            runs = [len(match.group()) for match in re.finditer(r"~+", value)]
            longest = max([longest, *runs])
    return "~" * max(3, longest + 1)


def _render_block(heading: str, value: str, fence: str) -> list[str]:
    return [heading, f"{fence}text", value, fence]


def render_translation_unit(unit: TranslationUnit) -> str:
    """Render a deterministic Markdown translation form."""
    if unit.component not in COMPONENTS:
        raise LocaleToolError(f"Unsupported DSW component: {unit.component!r}")
    if unit.kind not in {"message", "runtime"}:
        raise LocaleToolError(f"Unsupported translation unit kind: {unit.kind!r}")
    if not unit.msgid:
        raise LocaleToolError("Translation unit source text must not be empty")

    metadata = {
        "component": unit.component,
        "kind": unit.kind,
        "msgctxt": unit.msgctxt,
        "source_hash": source_hash(unit),
    }
    fence = _fence_for(unit.msgid, unit.msgid_plural, unit.translation)
    lines = [
        "# Translation",
        "",
        METADATA_PREFIX
        + json.dumps(metadata, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + METADATA_SUFFIX,
        "",
        INSTRUCTIONS,
        "",
        *_render_block(SOURCE_HEADING, unit.msgid, fence),
        "",
    ]
    if unit.msgid_plural is not None:
        lines.extend(_render_block(PLURAL_HEADING, unit.msgid_plural, fence))
        lines.append("")
    lines.extend(_render_block(TRANSLATION_HEADING, unit.translation, fence))
    return "\n".join(lines) + "\n"


def _parse_block(lines: list[str], index: int, heading: str, path: Path) -> tuple[str, int]:
    if index >= len(lines) or lines[index] != heading:
        raise LocaleToolError(f"Expected {heading!r} in translation unit: {path}")
    if index + 1 >= len(lines) or (match := FENCE_PATTERN.fullmatch(lines[index + 1])) is None:
        raise LocaleToolError(f"Expected a tilde text fence after {heading!r}: {path}")
    fence = match.group("fence")
    end = index + 2
    while end < len(lines) and lines[end] != fence:
        end += 1
    if end == len(lines):
        raise LocaleToolError(f"Unclosed {heading!r} block in translation unit: {path}")
    return "\n".join(lines[index + 2 : end]), end + 1


def parse_translation_unit(path: Path, repository_root: Path) -> TranslationUnit:
    """Parse and validate one strict Markdown translation form."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise LocaleToolError(f"Unable to read translation unit {path}: {error}") from error
    if not content.endswith("\n"):
        raise LocaleToolError(f"Translation unit must end with a newline: {path}")
    lines = content[:-1].split("\n")
    if len(lines) < 13 or lines[0] != "# Translation" or lines[1] != "":
        raise LocaleToolError(f"Invalid translation unit header: {path}")
    metadata_line = lines[2]
    if not metadata_line.startswith(METADATA_PREFIX) or not metadata_line.endswith(METADATA_SUFFIX):
        raise LocaleToolError(f"Invalid translation unit metadata: {path}")
    try:
        metadata = json.loads(metadata_line[len(METADATA_PREFIX) : -len(METADATA_SUFFIX)])
    except json.JSONDecodeError as error:
        raise LocaleToolError(
            f"Invalid translation unit metadata JSON in {path}: {error}"
        ) from error
    if not isinstance(metadata, dict) or set(metadata) != {
        "component",
        "kind",
        "msgctxt",
        "source_hash",
    }:
        raise LocaleToolError(f"Translation unit metadata has unexpected fields: {path}")
    component = metadata["component"]
    kind = metadata["kind"]
    msgctxt = metadata["msgctxt"]
    expected_hash = metadata["source_hash"]
    if (
        not isinstance(component, str)
        or component not in COMPONENTS
        or not isinstance(kind, str)
        or kind not in {"message", "runtime"}
    ):
        raise LocaleToolError(f"Translation unit metadata has unsupported values: {path}")
    if msgctxt is not None and not isinstance(msgctxt, str):
        raise LocaleToolError(f"Translation unit context must be text or null: {path}")
    if not isinstance(expected_hash, str) or not HASH_PATTERN.fullmatch(expected_hash):
        raise LocaleToolError(f"Translation unit source_hash is invalid: {path}")
    if lines[3:6] != ["", INSTRUCTIONS, ""]:
        raise LocaleToolError(f"Translation unit instructions were modified: {path}")

    msgid, index = _parse_block(lines, 6, SOURCE_HEADING, path)
    if index >= len(lines) or lines[index] != "":
        raise LocaleToolError(f"Expected spacing after source block: {path}")
    index += 1
    msgid_plural: str | None = None
    if index < len(lines) and lines[index] == PLURAL_HEADING:
        msgid_plural, index = _parse_block(lines, index, PLURAL_HEADING, path)
        if index >= len(lines) or lines[index] != "":
            raise LocaleToolError(f"Expected spacing after plural source block: {path}")
        index += 1
    translation, index = _parse_block(lines, index, TRANSLATION_HEADING, path)
    if index != len(lines):
        raise LocaleToolError(f"Unexpected content after translation block: {path}")

    unit = TranslationUnit(
        component=component,
        kind=kind,
        msgid=msgid,
        msgctxt=msgctxt,
        msgid_plural=msgid_plural,
        translation=translation,
    )
    if not msgid:
        raise LocaleToolError(f"Translation unit source text must not be empty: {path}")
    if source_hash(unit) != expected_hash:
        raise LocaleToolError(f"Translation unit source or identity was modified: {path}")
    expected_path = repository_root / unit_relative_path(unit)
    if path.resolve() != expected_path.resolve():
        raise LocaleToolError(f"Translation unit path must be {expected_path}: {path}")
    return unit


def _load_translation_tree(
    root: str | Path, *, validate_generated_index: bool
) -> dict[UnitKey, TranslationUnit]:
    repository_root = Path(root).resolve()
    translations_root = repository_root / TRANSLATIONS_DIRECTORY
    if translations_root.is_symlink() or not translations_root.is_dir():
        raise LocaleToolError(f"Translation tree does not exist: {translations_root}")

    index_path = translations_root / "README.md"
    if index_path.is_symlink() or not index_path.is_file():
        raise LocaleToolError(f"Generated translation index does not exist: {index_path}")
    paths: list[Path] = []
    for path in translations_root.rglob("*"):
        if path.is_symlink():
            raise LocaleToolError(f"Translation tree must not contain symlinks: {path}")
        if path.is_dir():
            continue
        if path == index_path:
            continue
        if not path.name.endswith(UNIT_SUFFIX):
            raise LocaleToolError(f"Unexpected file in translation tree: {path}")
        paths.append(path)

    units: dict[UnitKey, TranslationUnit] = {}
    for path in sorted(paths):
        unit = parse_translation_unit(path, repository_root)
        if unit.key in units:
            raise LocaleToolError(f"Duplicate translation unit identity: {unit.key!r}")
        units[unit.key] = unit
    if validate_generated_index and index_path.read_text(encoding="utf-8") != _render_index(units):
        raise LocaleToolError(f"Generated translation index is out of date: {index_path}")
    return units


def load_translation_tree(root: str | Path) -> dict[UnitKey, TranslationUnit]:
    """Load every translation unit and reject unknown or stale tree content."""
    return _load_translation_tree(root, validate_generated_index=True)


def _entry_translation(entry: polib.POEntry) -> str:
    values = translated_strings(entry)
    if len(values) != 1:
        raise LocaleToolError(
            f"Traditional Chinese translation must have exactly one plural form: {entry.msgid!r}"
        )
    return values[0]


def _entry_unit(component: str, entry: polib.POEntry, translation: str = "") -> TranslationUnit:
    return TranslationUnit(
        component=component,
        kind="message",
        msgid=entry.msgid,
        msgctxt=entry.msgctxt,
        msgid_plural=entry.msgid_plural or None,
        translation=translation,
    )


def _same_upstream_translation(unit: TranslationUnit, entry: polib.POEntry | None) -> bool:
    return bool(
        unit.translation
        and entry_is_translated(entry)
        and entry is not None
        and unit.translation == _entry_translation(entry)
    )


def desired_translation_units(
    root: str | Path,
    current: dict[UnitKey, TranslationUnit],
) -> dict[UnitKey, TranslationUnit]:
    """Resolve the exact tree required by the current official baseline."""
    repository_root = Path(root).resolve()
    desired: dict[UnitKey, TranslationUnit] = {}
    template_keys: set[UnitKey] = set()

    for component in COMPONENTS:
        template = load_catalog(repository_root / "upstream" / f"{component}.pot")
        baseline = load_catalog(repository_root / "upstream" / f"{component}.po")
        baseline_index = catalog_index(baseline)
        for entry in template:
            if entry.obsolete or not entry.msgid:
                continue
            key: UnitKey = (component, *entry_key(entry))
            template_keys.add(key)
            previous = current.get(key)
            current_plural = entry.msgid_plural or None
            if (
                previous is not None
                and previous.msgid_plural != current_plural
                and previous.translation
            ):
                raise LocaleToolError(
                    "Translated plural source changed upstream; resolve it explicitly: "
                    f"{entry.msgid!r}"
                )
            translation = previous.translation if previous is not None else ""
            unit = _entry_unit(component, entry, translation)
            baseline_entry = baseline_index.get(entry_key(entry))
            if not entry_is_translated(baseline_entry):
                desired[key] = unit
            elif (
                previous is not None
                and translation
                and not _same_upstream_translation(previous, baseline_entry)
            ):
                desired[key] = unit

    for key, unit in current.items():
        if key in template_keys:
            continue
        if unit.kind == "runtime":
            desired[key] = unit
        elif unit.translation:
            raise LocaleToolError(
                "Translated source no longer exists upstream; resolve it explicitly: "
                f"{unit.msgid!r}"
            )
    return desired


def _render_index(units: dict[UnitKey, TranslationUnit]) -> str:
    lines = [
        "# Translation forms",
        "",
        "Choose an open form and edit only its translation block.",
    ]
    for component in COMPONENTS:
        component_units = sorted(
            (unit for unit in units.values() if unit.component == component),
            key=lambda unit: (unit.msgid.casefold(), unit.msgctxt or ""),
        )
        open_units = [unit for unit in component_units if not unit.translation]
        completed_units = [unit for unit in component_units if unit.translation]
        lines.extend(
            [
                "",
                f"## {component.capitalize()}",
                "",
                f"{len(open_units)} open · {len(completed_units)} completed",
                "",
                f"### Open ({len(open_units)})",
                "",
            ]
        )
        if not component_units:
            lines.append("No open forms.")
            continue
        if not open_units:
            lines.append("No open forms.")
        for unit in open_units:
            lines.append(_render_index_entry(unit))
        lines.extend(["", f"### Completed ({len(completed_units)})", ""])
        if not completed_units:
            lines.append("No completed forms.")
        for unit in completed_units:
            lines.append(_render_index_entry(unit))
    return "\n".join(lines) + "\n"


def _render_index_entry(unit: TranslationUnit) -> str:
    relative = unit_relative_path(unit).relative_to(TRANSLATIONS_DIRECTORY)
    label = unit.msgid.replace("\n", " ").strip()
    if len(label) > 100:
        label = label[:97].rstrip() + "..."
    suffix = " (runtime-only)" if unit.kind == "runtime" else ""
    return f"- [{label}]({relative.as_posix()}){suffix}"


def write_translation_tree(
    root: str | Path,
    units: dict[UnitKey, TranslationUnit],
) -> None:
    """Atomically write a complete, deterministic translation tree."""
    repository_root = Path(root).resolve()
    translations_root = repository_root / TRANSLATIONS_DIRECTORY
    if any(key != unit.key for key, unit in units.items()):
        raise LocaleToolError("Translation tree mapping contains an incorrect unit key")

    temporary = repository_root / f".{TRANSLATIONS_DIRECTORY}.new"
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir()
    try:
        for unit in sorted(units.values(), key=lambda item: unit_relative_path(item).as_posix()):
            path = temporary / unit_relative_path(unit).relative_to(TRANSLATIONS_DIRECTORY)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render_translation_unit(unit), encoding="utf-8")
        (temporary / "README.md").write_text(_render_index(units), encoding="utf-8")
        if translations_root.exists():
            shutil.rmtree(translations_root)
        temporary.rename(translations_root)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def refresh_translation_tree(root: str | Path) -> dict[str, int]:
    """Regenerate translation forms from the official baseline without losing translations."""
    repository_root = Path(root).resolve()
    translations_root = repository_root / TRANSLATIONS_DIRECTORY
    current = (
        _load_translation_tree(repository_root, validate_generated_index=False)
        if translations_root.exists()
        else {}
    )
    desired = desired_translation_units(repository_root, current)
    write_translation_tree(repository_root, desired)

    return {
        "units": len(desired),
        "completed": sum(bool(unit.translation) for unit in desired.values()),
        "blank": sum(not unit.translation for unit in desired.values()),
        "runtime_only": sum(unit.kind == "runtime" for unit in desired.values()),
    }


def add_runtime_translation(
    root: str | Path,
    component: str,
    msgid: str,
    translation: str,
    *,
    msgctxt: str | None = None,
) -> Path:
    """Add one confirmed runtime-only source and regenerate the tree index."""
    if component not in COMPONENTS:
        raise LocaleToolError(f"Unsupported DSW component: {component!r}")
    if not msgid:
        raise LocaleToolError("Runtime-only source text must not be empty")
    repository_root = Path(root).resolve()
    template = load_catalog(repository_root / "upstream" / f"{component}.pot")
    if (msgctxt, msgid) in catalog_index(template):
        raise LocaleToolError(f"Runtime-only source already exists in upstream POT: {msgid!r}")

    units = load_translation_tree(repository_root)
    unit = TranslationUnit(
        component=component,
        kind="runtime",
        msgid=msgid,
        msgctxt=msgctxt,
        translation=translation,
    )
    if unit.key in units:
        raise LocaleToolError(f"Translation form already exists for source: {msgid!r}")
    units[unit.key] = unit
    write_translation_tree(repository_root, units)
    return repository_root / unit_relative_path(unit)


def build_component_catalog(root: str | Path, component: str) -> polib.POFile:
    """Apply completed Markdown units to one official PO catalog."""
    if component not in COMPONENTS:
        raise LocaleToolError(f"Unsupported DSW component: {component!r}")
    repository_root = Path(root).resolve()
    template = load_catalog(repository_root / "upstream" / f"{component}.pot")
    result = copy.deepcopy(load_catalog(repository_root / "upstream" / f"{component}.po"))
    template_index = catalog_index(template)
    result_index = catalog_index(result)
    units = {
        key: unit
        for key, unit in load_translation_tree(repository_root).items()
        if unit.component == component
    }

    for entry in template:
        if entry.obsolete or not entry.msgid:
            continue
        key: UnitKey = (component, *entry_key(entry))
        baseline_entry = result_index.get(entry_key(entry))
        if not entry_is_translated(baseline_entry) and key not in units:
            raise LocaleToolError(f"Missing translation form for source: {entry.msgid!r}")

    for unit in units.values():
        catalog_key = (unit.msgctxt, unit.msgid)
        template_entry = template_index.get(catalog_key)
        if unit.kind == "message" and template_entry is None:
            raise LocaleToolError(
                f"Translation form source is absent from upstream: {unit.msgid!r}"
            )
        if unit.kind == "runtime" and template_entry is not None:
            raise LocaleToolError(f"Runtime-only source is now present upstream: {unit.msgid!r}")
        if not unit.translation:
            continue

        existing = result_index.get(catalog_key)
        if existing is not None and _same_upstream_translation(unit, existing):
            raise LocaleToolError(f"Local translation is identical to upstream: {unit.msgid!r}")
        replacement = copy.deepcopy(template_entry or existing)
        if replacement is None:
            replacement = polib.POEntry(
                msgid=unit.msgid,
                msgctxt=unit.msgctxt,
                msgid_plural=unit.msgid_plural or "",
            )
        replacement.flags = [flag for flag in replacement.flags if flag != "fuzzy"]
        replacement.msgstr = "" if unit.msgid_plural else unit.translation
        replacement.msgstr_plural = {"0": unit.translation} if unit.msgid_plural else {}
        if existing is None:
            result.append(replacement)
        else:
            result[result.index(existing)] = replacement
        result_index[catalog_key] = replacement
    return result
