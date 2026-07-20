"""Isolation policy tests for the host-ready review stack."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "review" / "docker-compose.yml"
GATEWAY = ROOT / "review" / "gateway" / "nginx.conf"


def test_only_gateway_has_a_loopback_host_port():
    compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    exposed = {
        name: service["ports"]
        for name, service in compose["services"].items()
        if "ports" in service
    }

    assert exposed == {"gateway": ["127.0.0.1:${DSW_REVIEW_PORT:-8088}:8080"]}
    assert compose["networks"]["internal"]["internal"] is True
    assert set(compose["services"]["gateway"]["networks"]) == {"edge", "internal"}
    for name in ("server", "client", "postgres", "minio"):
        assert compose["services"][name]["networks"] == ["internal"]


def test_review_gateway_is_read_only_and_the_setup_tool_is_ephemeral():
    compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    gateway = compose["services"]["gateway"]
    review_tool = compose["services"]["review-tool"]

    assert gateway["read_only"] is True
    assert gateway["cap_drop"] == ["ALL"]
    assert review_tool["profiles"] == ["setup"]
    assert review_tool["read_only"] is True
    assert review_tool["cap_drop"] == ["ALL"]
    assert all("production" not in volume for volume in review_tool["volumes"])


def test_gateway_allows_one_login_write_and_denies_other_mutations_and_websockets():
    nginx = GATEWAY.read_text(encoding="utf-8")

    assert "location = /wizard-api/tokens" in nginx
    assert "limit_except POST OPTIONS { deny all; }" in nginx
    assert "limit_except GET HEAD OPTIONS { deny all; }" in nginx
    assert "map_hash_bucket_size 256;" in nginx
    assert "location ~ ^/wizard-api/projects/[^/]+/websocket$" in nginx
    assert "if ($review_is_upgrade) { return 403; }" in nginx
    assert "if ($review_route_allowed = 0) { return 404; }" in nginx
    assert "include /opt/dsw-review/runtime/site/allowed-routes.map;" in nginx


def test_client_uses_the_public_same_origin_api_and_review_mode_injection():
    compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    client = compose["services"]["client"]

    assert client["environment"]["API_URL"].endswith("/wizard-api")
    assert "./client/head-extra.html:/src/head-extra.html:ro" in client["volumes"]
    assert (ROOT / "review" / "client" / "head-extra.html").is_file()

    review_mode = (ROOT / "src" / "dsw_locale_tool" / "review_site" / "review-mode.js").read_text(
        encoding="utf-8"
    )
    assert "destination.origin === window.location.origin" in review_mode


def test_launcher_makes_generated_config_readable_by_the_versioned_server_user():
    launcher = (ROOT / "review" / "up.sh").read_text(encoding="utf-8")

    assert 'chmod 644 -- "$runtime_dir/application.yml"' in launcher
