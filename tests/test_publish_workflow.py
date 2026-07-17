"""Release workflow safety policy tests."""

from __future__ import annotations

from pathlib import Path

WORKFLOWS = Path(__file__).parents[1] / ".github" / "workflows"


def test_publisher_is_scheduled_and_never_overwrites_a_tag():
    publisher = (WORKFLOWS / "publish-installer.yml").read_text(encoding="utf-8")
    release = (WORKFLOWS / "publish-installer-release.yml").read_text(encoding="utf-8")

    assert 'cron: "17 4 * * *"' in publisher
    assert "description: Version branch, tag, or commit" not in publisher
    assert "description: Key in translation-config.yml" not in publisher
    assert "dsw-locale release-info" in release
    assert "docker/login-action@v4" in release
    assert "docker/build-push-action@v7" in release
    assert "docker/login-action@v3" not in release
    assert "docker/build-push-action@v6" not in release
    assert 'docker buildx imagetools inspect "$IMAGE_REFERENCE"' in release
    assert 'echo "publish=false"' in release
    assert "if: steps.tag.outputs.publish == 'true'" in release
    assert "tags: ${{ steps.image.outputs.reference }}" in release
    assert "org.opencontainers.image.revision=${{ steps.image.outputs.revision }}" in release
    assert "load: true" in release
    assert "Smoke test installer image" in release
    assert ".created == true and .enabled == true and .defaultLocale == true" in release
    assert ".created == false and .enabled == true and .defaultLocale == true" in release
    assert 'run: docker push "$IMAGE_REFERENCE"' in release
