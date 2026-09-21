"""Workflow boundaries and CLI contract."""

from pathlib import Path

import yaml

from dsw_locale_tool.cli import parser

ROOT = Path(__file__).parents[1]


def workflow(name):
    return yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)


def test_sync_has_no_runtime_dependency_or_web_credentials():
    data = workflow("sync-weblate.yml")
    text = str(data)
    assert data["permissions"] == {"contents": "write"}
    for forbidden in ("docker", "npm", "LOCALIZE_API_TOKEN", "build-source"):
        assert forbidden not in text


def test_submission_is_explicit_and_scoped():
    data = workflow("submit-weblate.yml")
    inputs = data["on"]["workflow_call"]["inputs"]
    assert inputs["apply"]["default"] == "false"
    assert inputs["allow_corrections"]["default"] == "false"
    assert "expected_plan" in inputs
    assert data["permissions"] == {"contents": "read"}
    assert set(data["on"]["workflow_call"]["secrets"]) == {"LOCALIZE_API_TOKEN"}


def test_pr_checks_have_no_write_permissions_or_secret():
    data = workflow("check-translations.yml")
    assert data["permissions"] == {"contents": "read"}
    assert "secrets" not in data["on"]["workflow_call"]
    assert "pip install ./head" not in str(data)
    assert "persist-credentials': 'false'" in str(data)


def test_workflows_use_executable_bash_syntax(tmp_path):
    import subprocess

    for path in (ROOT / ".github/workflows").glob("*.yml"):
        data = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
        for job in data.get("jobs", {}).values():
            for step in job.get("steps", []):
                if "run" in step:
                    result = subprocess.run(
                        ["bash", "-n"], input=step["run"], text=True, capture_output=True
                    )
                    assert result.returncode == 0, (path.name, result.stderr)


def test_read_only_submission_is_default():
    args = parser().parse_args(["submit", "--config", "config.yml", "--version", "v4.34"])
    assert not args.apply
    assert not args.allow_corrections
    assert args.limit == 20
