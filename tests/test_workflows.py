"""GitHub Actions workflow syntax tests."""

from __future__ import annotations

from pathlib import Path

import yaml


def test_all_workflows_are_valid_yaml():
    workflows = Path(__file__).parents[1] / ".github" / "workflows"

    for workflow in workflows.glob("*.yml"):
        assert isinstance(
            yaml.load(workflow.read_text(encoding="utf-8"), Loader=yaml.BaseLoader), dict
        )


def test_workflows_use_node_24_artifact_action():
    workflows = Path(__file__).parents[1] / ".github" / "workflows"

    for workflow in workflows.glob("*.yml"):
        contents = workflow.read_text(encoding="utf-8")
        assert "actions/upload-artifact@v4" not in contents
        if "actions/upload-artifact@" in contents:
            assert "actions/upload-artifact@v7" in contents


def test_supported_preview_matrix_is_derived_from_translation_config():
    workflow = (
        Path(__file__).parents[1] / ".github" / "workflows" / "preview-supported.yml"
    ).read_text(encoding="utf-8")

    assert "dsw-locale preview-matrix --config locale/translation-config.yml" in workflow
    assert "matrix.config_version" in workflow
    for version in ("v4.29", "v4.30", "v4.31", "v4.32"):
        assert version not in workflow
