"""Release workflow safety policy tests."""

from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "publish-installer.yml"


def test_installer_tag_is_derived_and_immutable():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "image_tag:" not in workflow
    assert 'tool/build/locale/locale.json"))["version"]' in workflow
    assert "Refuse to overwrite an immutable tag" in workflow
    assert 'docker buildx imagetools inspect "$IMAGE_REFERENCE"' in workflow
    assert "tags: ${{ steps.image.outputs.reference }}" in workflow
