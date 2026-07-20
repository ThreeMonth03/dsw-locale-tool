"""Download and verify immutable content used by DSW locale previews."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

import requests

from dsw_locale_tool.config import PreviewArtifact, TranslationConfig
from dsw_locale_tool.errors import LocaleToolError

Downloader = Callable[[str], bytes]


def fetch_preview_content(
    config: TranslationConfig,
    version_key: str,
    output: str | Path,
    *,
    downloader: Downloader | None = None,
) -> dict[str, str]:
    """Download the configured KM and document template after hash checks."""

    preview = config.preview(version_key)
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)
    download = downloader or _download
    knowledge_model_path = _fetch_artifact(
        preview.knowledge_model,
        output_dir / "knowledge-model.km",
        download,
    )
    document_template_path = _fetch_artifact(
        preview.document_template,
        output_dir / "document-template.zip",
        download,
    )
    return {
        "knowledge_model": str(knowledge_model_path),
        "document_template": str(document_template_path),
        "document_format_uuid": preview.document_format_uuid,
    }


def _fetch_artifact(
    artifact: PreviewArtifact,
    destination: Path,
    downloader: Downloader,
) -> Path:
    content = downloader(artifact.url)
    actual_sha256 = hashlib.sha256(content).hexdigest()
    if actual_sha256 != artifact.sha256:
        raise LocaleToolError(
            f"Preview artifact checksum mismatch for {artifact.url}: "
            f"expected {artifact.sha256}, got {actual_sha256}"
        )
    destination.write_bytes(content)
    return destination


def _download(url: str) -> bytes:
    try:
        response = requests.get(url, timeout=120)
        response.raise_for_status()
    except requests.RequestException as error:
        raise LocaleToolError(f"Unable to download preview artifact {url}: {error}") from error
    return response.content
