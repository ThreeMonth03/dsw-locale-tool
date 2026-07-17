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

    assert "dsw-locale maintained-matrix --config locale/translation-config.yml" in planner
    assert "plan-maintained-releases.yml" in preview
    assert "plan-maintained-releases.yml" in publisher
    assert "matrix.config_version" in preview
    assert "matrix.config_version" in publisher
    for version in ("v4.29", "v4.30", "v4.31", "v4.32"):
        assert version not in planner
        assert version not in preview
        assert version not in publisher
