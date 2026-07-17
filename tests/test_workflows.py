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
