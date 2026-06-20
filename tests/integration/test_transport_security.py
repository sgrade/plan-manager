# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""Regression tests for DNS-rebinding (Host header) handling.

Sibling containers (e.g. devcontainers) connect via `host.docker.internal`.
FastMCP's transport security must allow that host, otherwise the request is
rejected with HTTP 421 before reaching any tool.
"""

import pytest
from starlette.testclient import TestClient

from plan_manager.server.app import starlette_app

_INIT_BODY = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0.0.0"},
    },
}
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def _post(host: str):
    # Context manager runs the app lifespan so the streamable-http session
    # manager's task group is initialized for allowed-host requests.
    with TestClient(starlette_app()) as client:
        return client.post(
            "/mcp",
            json=_INIT_BODY,
            headers={**_HEADERS, "Host": host},
        )


@pytest.mark.integration
@pytest.mark.parametrize("host", ["host.docker.internal:8105", "127.0.0.1:3000"])
def test_allowed_hosts_not_rejected(host):
    """Loopback and the docker host pass Host validation (no 421)."""
    assert _post(host).status_code != 421


@pytest.mark.integration
def test_disallowed_host_returns_421():
    """An unknown Host header is rejected before reaching any tool."""
    resp = _post("evil.example.com:8105")
    assert resp.status_code == 421
