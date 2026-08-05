# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""Integration coverage for stateless Streamable HTTP mode."""

import re

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
_INIT_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def _initialize(client: TestClient, correlation_id: str | None = None):
    headers = dict(_INIT_HEADERS)
    if correlation_id is not None:
        headers["x-correlation-id"] = correlation_id
    return client.post("/mcp", json=_INIT_BODY, headers=headers)


@pytest.mark.integration
def test_streamable_http_stateless_json_mode_and_routes():
    """Initialize works repeatedly in stateless mode and routes stay healthy."""
    with TestClient(starlette_app(), base_url="http://127.0.0.1:3000") as client:
        first = _initialize(client)
        assert first.status_code == 200
        assert first.headers["content-type"].startswith("application/json")
        assert first.json()["jsonrpc"] == "2.0"
        assert "result" in first.json()
        assert "mcp-session-id" not in first.headers
        assert first.headers.get("x-correlation-id")

        second_correlation_id = "corr-test-2"
        second = _initialize(client, correlation_id=second_correlation_id)
        assert second.status_code == 200
        assert second.headers["content-type"].startswith("application/json")
        assert second.json()["jsonrpc"] == "2.0"
        assert "result" in second.json()
        assert "mcp-session-id" not in second.headers
        assert second.headers.get("x-correlation-id") == second_correlation_id

        health_correlation_id = "health-corr"
        health = client.get(
            "/health", headers={"x-correlation-id": health_correlation_id}
        )
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}
        assert health.headers.get("x-correlation-id") == health_correlation_id

        root = client.get("/", follow_redirects=False)
        assert root.status_code in {302, 307}
        assert root.headers["location"] == "/ui"

        browse = client.get("/browse")
        assert browse.status_code == 404


@pytest.mark.integration
def test_streamable_http_stateless_concurrent_initializes():
    """Parallel initializes all succeed: no session pinning, no creation lock.

    Regression canary for the stateful-mode wedge where the SDK serialized all
    new-session initializes behind a global lock (tracker: binding item 2).
    """
    from concurrent.futures import ThreadPoolExecutor

    with TestClient(starlette_app(), base_url="http://127.0.0.1:3000") as client:
        correlation_ids = [f"conc-corr-{i}" for i in range(8)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(
                pool.map(lambda c: _initialize(client, c), correlation_ids)
            )

        for corr_id, resp in zip(correlation_ids, responses):
            assert resp.status_code == 200
            assert "result" in resp.json()
            assert "mcp-session-id" not in resp.headers
            assert resp.headers.get("x-correlation-id") == corr_id


@pytest.mark.integration
def test_invalid_correlation_id_is_replaced_with_uuid():
    with TestClient(starlette_app(), base_url="http://127.0.0.1:3000") as client:
        resp = _initialize(client, correlation_id='bad-id"><script>alert(1)</script>')
    assert resp.status_code == 200
    corr_id = resp.headers.get("x-correlation-id")
    assert corr_id is not None
    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        corr_id,
    )
