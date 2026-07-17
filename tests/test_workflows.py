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
