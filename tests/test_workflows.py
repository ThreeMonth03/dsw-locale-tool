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


def test_maintained_matrix_is_derived_from_translation_config():
    workflows = Path(__file__).parents[1] / ".github" / "workflows"
    planner = (workflows / "plan-maintained-releases.yml").read_text(encoding="utf-8")
    preview = (workflows / "preview-supported.yml").read_text(encoding="utf-8")
    publisher = (workflows / "publish-installer.yml").read_text(encoding="utf-8")

    assert "dsw-locale maintained-matrix --config locale/translation-config.yml" in planner
    assert "plan-maintained-releases.yml" in preview
    assert "plan-maintained-releases.yml" in publisher
    assert "matrix.config_version" in preview
    assert "matrix.config_version" in publisher
    for version in ("v4.29", "v4.30", "v4.31", "v4.32"):
        assert version not in planner
        assert version not in preview
        assert version not in publisher
