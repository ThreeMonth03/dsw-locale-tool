"""GitHub Actions workflow syntax tests."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

EXTERNAL_ACTION = re.compile(r"^\s*uses:\s+([^@\s]+)@([^\s#]+)", re.MULTILINE)
EXPECTED_EXTERNAL_ACTIONS = {
    ("actions/checkout", "v6"),
    ("actions/configure-pages", "v6"),
    ("actions/deploy-pages", "v5"),
    ("actions/setup-node", "v6"),
    ("actions/setup-python", "v6"),
    ("actions/upload-artifact", "v7"),
    ("actions/upload-pages-artifact", "v5"),
    ("docker/build-push-action", "v7"),
    ("docker/login-action", "v4"),
    ("docker/setup-buildx-action", "v4"),
    ("docker/setup-qemu-action", "v4"),
}


def test_all_workflows_are_valid_yaml():
    workflows = Path(__file__).parents[1] / ".github" / "workflows"

    for workflow in workflows.glob("*.yml"):
        assert isinstance(
            yaml.load(workflow.read_text(encoding="utf-8"), Loader=yaml.BaseLoader), dict
        )


def test_workflows_use_current_external_action_majors():
    workflows = Path(__file__).parents[1] / ".github" / "workflows"
    actual: set[tuple[str, str]] = set()

    for workflow in workflows.glob("*.yml"):
        contents = workflow.read_text(encoding="utf-8")
        actual.update(EXTERNAL_ACTION.findall(contents))

    assert actual == EXPECTED_EXTERNAL_ACTIONS


def test_maintained_matrix_is_derived_from_translation_config():
    workflows = Path(__file__).parents[1] / ".github" / "workflows"
    planner = (workflows / "plan-maintained-releases.yml").read_text(encoding="utf-8")
    preview = (workflows / "preview-supported.yml").read_text(encoding="utf-8")
    publisher = (workflows / "publish-installer.yml").read_text(encoding="utf-8")
    propagation = (workflows / "propagate-locale.yml").read_text(encoding="utf-8")

    assert "dsw-locale maintained-matrix --config locale/translation-config.yml" in planner
    assert "plan-maintained-releases.yml" in preview
    assert "plan-maintained-releases.yml" in publisher
    assert "dsw-locale maintained-matrix" in propagation
    assert "select(.translation_ref != $source)" in propagation
    assert "dsw-locale bump-release" in propagation
    assert "needs.prepare.outputs.translation_changed == 'true'" in propagation
    assert "matrix.config_version" in preview
    assert "matrix.config_version" in publisher
    for version in ("v4.29", "v4.30", "v4.31", "v4.32"):
        assert version not in planner
        assert version not in preview
        assert version not in publisher
        assert version not in propagation


def test_locale_pr_validation_exposes_preview_coordinates():
    workflow = (
        Path(__file__).parents[1] / ".github" / "workflows" / "validate-locale-pr.yml"
    ).read_text(encoding="utf-8")

    assert "value: ${{ jobs.validate.outputs.config_version }}" in workflow
    assert "value: ${{ jobs.validate.outputs.dsw_image_tag }}" in workflow
    assert "value: ${{ jobs.validate.outputs.translation_changed }}" in workflow
    assert "dsw-locale refresh-tree --root locale" in workflow


def test_ci_validates_review_compose_and_real_nginx_configuration():
    workflow = (Path(__file__).parents[1] / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "docker compose --file review/docker-compose.yml config --quiet" in workflow
    assert "generate_review_site" in workflow
    assert "nginx:1.28-alpine nginx -t" in workflow


def test_live_preview_uses_a_unique_tunnel_and_bounded_activity_lifecycle():
    root = Path(__file__).parents[1]
    workflow = (root / ".github" / "workflows" / "live-preview.yml").read_text(encoding="utf-8")
    gateway = (root / "review" / "gateway" / "nginx.conf").read_text(encoding="utf-8")

    assert "cloudflare/cloudflared:2026.7.0" in workflow
    assert "dsw-live-tunnel-${{ github.run_id }}-${{ github.run_attempt }}" in workflow
    assert "timeout-minutes: 240" in workflow
    assert "default: 30" in workflow
    assert "default: 180" in workflow
    assert "DSW_ADMIN_PASSWORD: password" in workflow
    assert "tool/review/up.sh" in workflow
    assert "python -m playwright install --with-deps chromium" in workflow
    assert "dsw-locale verify-review-browser" in workflow
    assert "dsw-locale wait-review" in workflow
    assert "tool/review/down.sh" in workflow
    assert "update-pr-comment.sh ready" in workflow
    assert "dsw-locale fetch-preview-content" in workflow
    assert "DSW_REVIEW_DOCUMENT_TEMPLATE" in workflow
    assert "translation_control_repository" in workflow
    assert "translation_control_ref" in workflow
    assert "--config control/translation-config.yml" in workflow
    assert "DSW_REVIEW_HEARTBEAT $msec" in gateway
    assert "location = /review/heartbeat" in gateway
    for version in ("v4.29", "v4.30", "v4.31", "v4.32"):
        assert version not in workflow


def test_preview_exercises_file_and_administration_interfaces():
    workflow = (
        Path(__file__).parents[1] / ".github" / "workflows" / "preview-locale.yml"
    ).read_text(encoding="utf-8")

    assert "file_knowledge_model_url" in workflow
    assert "cypress/fixtures/file-km.json" in workflow
    assert "--file-project-uuid" in workflow
    assert "--preview-file tool/preview/fixtures/preview.csv" in workflow
    assert "--allowed-content-json build/file-preview.km" in workflow
    assert "--review-manifest tool/review/pages.yml" in workflow
    assert "dsw-locale fetch-preview-content" in workflow
    assert "--document-template build/preview-content/document-template.zip" in workflow
    assert "--document-format-uuid" in workflow
    assert "translation_control_repository" in workflow
    assert "translation_control_ref" in workflow
    assert "--config control/translation-config.yml" in workflow
    assert "datastewardshipwizard/wizard-client:${{ inputs.dsw_image_tag }}" in workflow


def test_maintained_previews_use_the_control_configuration():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "preview-supported.yml").read_text(
        encoding="utf-8"
    )

    assert "translation_control_repository" in workflow
    assert "translation_control_ref" in workflow
    assert "translation_control_repository: ${{ inputs.translation_control_repository" in workflow
    assert "translation_control_ref: ${{ inputs.translation_control_ref || 'main' }}" in workflow
