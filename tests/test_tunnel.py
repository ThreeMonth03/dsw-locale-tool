"""Quick Tunnel launcher tests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]
LAUNCHER = ROOT / "review" / "start-tunnel.sh"


def fake_docker(tmp_path: Path) -> tuple[Path, Path]:
    """Create a deterministic Docker command for tunnel retry tests."""
    bin_directory = tmp_path / "bin"
    bin_directory.mkdir()
    state = tmp_path / "attempt"
    executable = bin_directory / "docker"
    executable.write_text(
        """#!/usr/bin/env bash
set -euo pipefail

state=${FAKE_DOCKER_STATE:?}
case $1 in
  rm)
    exit 0
    ;;
  run)
    attempt=0
    if [[ -f "$state" ]]; then
      attempt=$(<"$state")
    fi
    printf '%d\n' "$((attempt + 1))" > "$state"
    printf 'container-id\n'
    ;;
  logs)
    attempt=$(<"$state")
    if [[ "$attempt" == "${FAKE_DOCKER_SUCCEED_ATTEMPT:-0}" ]]; then
      printf 'https://translated-preview.trycloudflare.com\n'
    else
      printf 'temporary tunnel failure on attempt %s\n' "$attempt"
    fi
    ;;
  inspect)
    attempt=$(<"$state")
    if [[ "$attempt" == "${FAKE_DOCKER_SUCCEED_ATTEMPT:-0}" ]]; then
      printf 'true\n'
    else
      printf 'false\n'
    fi
    ;;
esac
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    sleep = bin_directory / "sleep"
    sleep.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    sleep.chmod(0o755)
    return bin_directory, state


def run_launcher(tmp_path: Path, succeed_attempt: int) -> subprocess.CompletedProcess[str]:
    """Run the launcher with the fake Docker command."""
    bin_directory, state = fake_docker(tmp_path)
    environment = os.environ.copy()
    environment["PATH"] = f"{bin_directory}:{environment['PATH']}"
    environment["FAKE_DOCKER_STATE"] = str(state)
    environment["FAKE_DOCKER_SUCCEED_ATTEMPT"] = str(succeed_attempt)
    return subprocess.run(
        [LAUNCHER, "cloudflared:test", "preview-tunnel", "18088"],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )


def test_tunnel_launcher_retries_an_early_container_exit(tmp_path):
    result = run_launcher(tmp_path, succeed_attempt=2)

    assert result.returncode == 0
    assert result.stdout == "https://translated-preview.trycloudflare.com\n"
    assert "attempt 1 failed; retrying" in result.stderr


def test_tunnel_launcher_reports_logs_after_all_attempts_fail(tmp_path):
    result = run_launcher(tmp_path, succeed_attempt=0)

    assert result.returncode == 1
    assert "failed after 5 attempts" in result.stderr
    assert "temporary tunnel failure on attempt 5" in result.stderr
