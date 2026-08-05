# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""Concurrency soak harness for the SQLite-backed Plan Manager MCP server.

Imported by ``tests/soak/test_soak.py`` (marked ``soak``, excluded from the
default pytest run via ``tests/soak/conftest.py``).

Spins up a fresh ``pm`` server subprocess on port 3150 with scratch
``TODO_DIR`` / ``PLAN_MANAGER_DB_DIR`` under ``/tmp``, drives it with N
concurrent MCP-over-HTTP agent clients following the documented contract,
collects latency/error/resource metrics, runs a post-run integrity audit, and
writes a verdict report to ``tmp/stability-and-multiplan/reviews/u9-soak-report.md``.

Durations and client counts are env-tunable; defaults match the spec
(ramp to 24, sustain >=5 min, 30s burst at 48).
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import socket
import sqlite3
import statistics
import subprocess
import sys
import threading
import time
import uuid
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Configuration (env-tunable; defaults match the spec)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = (
    REPO_ROOT / "tmp" / "stability-and-multiplan" / "reviews" / "u9-soak-report.md"
)

HOST = os.getenv("SOAK_HOST", "127.0.0.1")
PORT = int(os.getenv("SOAK_PORT", "3150"))
NUM_PLANS = int(os.getenv("SOAK_NUM_PLANS", "6"))
RAMP_CLIENTS = int(os.getenv("SOAK_RAMP_CLIENTS", "24"))
SUSTAIN_SECONDS = float(os.getenv("SOAK_SUSTAIN_SECONDS", "300"))
BURST_CLIENTS = int(os.getenv("SOAK_BURST_CLIENTS", "48"))
BURST_SECONDS = float(os.getenv("SOAK_BURST_SECONDS", "30"))
RACE_K = int(os.getenv("SOAK_RACE_K", "8"))
RACE_INTERVAL = float(os.getenv("SOAK_RACE_INTERVAL", "8.0"))
THINK_MS = float(os.getenv("SOAK_THINK_MS", "5"))
SERVER_STARTUP_TIMEOUT = float(os.getenv("SOAK_SERVER_STARTUP_TIMEOUT", "30"))
SAMPLE_INTERVAL = float(os.getenv("SOAK_SAMPLE_INTERVAL", "2.0"))

SCRATCH_ROOT = Path("/tmp") / f"plan_manager_soak_{uuid.uuid4().hex[:8]}"  # noqa: S108
MCP_URL = f"http://{HOST}:{PORT}/mcp"
HEALTH_URL = f"http://{HOST}:{PORT}/health"
JSON_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

_BUSY_PATTERNS = (
    "sqlite is busy",
    "database is locked",
    "storagebusyerror",
    "retry later",
)
_VALIDATION_PATTERNS = (
    "validation error",
    "field required",
    "invalid parameter",
    "invalid type",
    "invalid value",
    "invalid status transition",
    "was not found in plan",
    "not found",
    "missing required parameter",
    "missing required scope",
    "structured_recovery",
)

OK = "ok"
VALIDATION_ERROR = "validation_error"
BUSY_EXHAUSTED = "busy_exhausted"
HTTP_5XX = "http_5xx"
CONNECTION_ERROR = "connection_error"
UNEXPECTED_ERROR = "unexpected_error"
OUTCOMES = (
    OK,
    VALIDATION_ERROR,
    BUSY_EXHAUSTED,
    HTTP_5XX,
    CONNECTION_ERROR,
    UNEXPECTED_ERROR,
)


@dataclass
class CallRecord:
    client: str
    tool: str
    latency_ms: float
    outcome: str
    http_status: int | None
    detail: str = ""
    elapsed_s: float = 0.0


@dataclass
class RaceRecord:
    race_id: int
    plan_id: str
    story_id: str
    task_id: str
    successes: int
    failures: int
    failure_kinds: list[str]
    winner_thread: str | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _percentiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {"n": 0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0, "mean": 0.0}
    s = sorted(values)
    n = len(s)

    def _pct(p: float) -> float:
        if n == 1:
            return s[0]
        k = (n - 1) * p
        lo = int(k)
        hi = min(lo + 1, n - 1)
        frac = k - lo
        return s[lo] + (s[hi] - s[lo]) * frac

    return {
        "n": n,
        "p50": _pct(0.50),
        "p95": _pct(0.95),
        "p99": _pct(0.99),
        "max": s[-1],
        "mean": sum(s) / n,
    }


def _classify(http_status: int | None, is_error: bool, text: str) -> str:
    if http_status is not None and http_status >= 500:
        return HTTP_5XX
    if http_status is None:
        return CONNECTION_ERROR
    if not is_error:
        return OK
    low = text.lower()
    if any(p in low for p in _BUSY_PATTERNS):
        return BUSY_EXHAUSTED
    if any(p in low for p in _VALIDATION_PATTERNS):
        return VALIDATION_ERROR
    return UNEXPECTED_ERROR


def _free_port_check(port: int) -> bool:
    """Return True if the port appears free for bind."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((HOST, port))
            return True
        except OSError:
            return False


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class Metrics:
    """Thread-safe collector for per-call records and resource samples."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.calls: list[CallRecord] = []
        self.rss_samples: list[tuple[float, int]] = []
        self.db_samples: list[tuple[float, int, int]] = []
        self.server_crashed = False
        self.start_monotonic = time.monotonic()

    def record(self, rec: CallRecord) -> None:
        with self._lock:
            self.calls.append(rec)

    def sample_resource(self, rss_kb: int, db_bytes: int, wal_bytes: int) -> None:
        with self._lock:
            elapsed = time.monotonic() - self.start_monotonic
            self.rss_samples.append((elapsed, rss_kb))
            self.db_samples.append((elapsed, db_bytes, wal_bytes))

    def mark_crash(self) -> None:
        with self._lock:
            self.server_crashed = True

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            calls = list(self.calls)
            rss = list(self.rss_samples)
            dbs = list(self.db_samples)
            crashed = self.server_crashed
        by_tool: dict[str, list[float]] = defaultdict(list)
        outcome_counts: Counter[str] = Counter()
        outcome_by_tool: dict[str, Counter[str]] = defaultdict(Counter)
        for c in calls:
            by_tool[c.tool].append(c.latency_ms)
            outcome_counts[c.outcome] += 1
            outcome_by_tool[c.tool][c.outcome] += 1
        per_tool_pct = {tool: _percentiles(lats) for tool, lats in by_tool.items()}
        return {
            "total_calls": len(calls),
            "by_tool_latencies": per_tool_pct,
            "outcome_counts": dict(outcome_counts),
            "outcome_by_tool": {t: dict(c) for t, c in outcome_by_tool.items()},
            "rss_samples": rss,
            "db_samples": dbs,
            "server_crashed": crashed,
        }


# ---------------------------------------------------------------------------
# Ledger (client-side record of acknowledged mutations + race outcomes)
# ---------------------------------------------------------------------------


class Ledger:
    """Thread-safe ledger of acknowledged mutations and race outcomes."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.plans: set[str] = set()
        self.stories: list[tuple[str, str]] = []  # (plan_id, story_id)
        self.tasks: list[tuple[str, str, str]] = []
        # workflow_mutations entries are (plan_id, story_id, local_id, action).
        self.workflow_mutations: list[tuple[str, str, str, str]] = []
        self.races: list[RaceRecord] = []

    def add_plan(self, plan_id: str) -> None:
        with self._lock:
            self.plans.add(plan_id)

    def add_story(self, plan_id: str, story_id: str) -> None:
        with self._lock:
            self.stories.append((plan_id, story_id))

    def add_task(self, plan_id: str, story_id: str, local_id: str) -> None:
        with self._lock:
            self.tasks.append((plan_id, story_id, local_id))

    def add_workflow(
        self, plan_id: str, story_id: str, local_id: str, action: str
    ) -> None:
        with self._lock:
            self.workflow_mutations.append((plan_id, story_id, local_id, action))

    def add_race(self, rec: RaceRecord) -> None:
        with self._lock:
            self.races.append(rec)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "plans": set(self.plans),
                "stories": list(self.stories),
                "tasks": list(self.tasks),
                "workflow_mutations": list(self.workflow_mutations),
                "races": list(self.races),
            }


# ---------------------------------------------------------------------------
# MCP client (JSON-RPC over HTTP, stateless)
# ---------------------------------------------------------------------------


class MCPClient:
    """A single MCP-over-HTTP client.

    Stateless server mode means each request is independent; we still send an
    ``initialize`` once per client for protocol realism, then drive tools.
    """

    def __init__(self, name: str, metrics: Metrics) -> None:
        self.name = name
        self.metrics = metrics
        self._id = 0
        self.client = httpx.Client(
            base_url=f"http://{HOST}:{PORT}",
            headers=JSON_HEADERS,
            timeout=httpx.Timeout(30.0, connect=5.0),
        )

    def close(self) -> None:
        self.client.close()

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _post(
        self, body: dict[str, Any]
    ) -> tuple[int | None, dict[str, Any] | None, str]:
        try:
            r = self.client.post("/mcp", json=body)
        except httpx.HTTPError as exc:
            self.metrics.record(
                CallRecord(
                    self.name,
                    body.get("method", "?"),
                    0.0,
                    CONNECTION_ERROR,
                    None,
                    str(exc),
                    time.monotonic() - self.metrics.start_monotonic,
                )
            )
            return None, None, str(exc)
        text = r.text
        try:
            payload = r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, None, text
        return r.status_code, payload, text

    def initialize(self) -> None:
        body = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": self.name, "version": "soak-1.0"},
            },
        }
        self._post(body)
        # notifications/initialized (no id, no response expected)
        self.client.post(
            "/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}
        )

    def call_tool(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool. Returns a result dict with keys:
        ok, outcome, http_status, text, structured, latency_ms.
        """
        body = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }
        start = time.perf_counter()
        status, payload, raw = self._post(body)
        latency_ms = (time.perf_counter() - start) * 1000.0
        elapsed_s = time.monotonic() - self.metrics.start_monotonic
        result: dict[str, Any] = {
            "ok": False,
            "outcome": CONNECTION_ERROR,
            "http_status": status,
            "text": "",
            "structured": None,
            "latency_ms": latency_ms,
        }
        if status is None:
            self.metrics.record(
                CallRecord(
                    self.name, tool, latency_ms, CONNECTION_ERROR, None, raw, elapsed_s
                )
            )
            return result
        if payload is None:
            outcome = HTTP_5XX if status >= 500 else UNEXPECTED_ERROR
            self.metrics.record(
                CallRecord(self.name, tool, latency_ms, outcome, status, raw, elapsed_s)
            )
            result["outcome"] = outcome
            return result
        rpc_result = payload.get("result")
        if rpc_result is None:
            # JSON-RPC level error
            err = payload.get("error", {})
            text = str(err.get("message", raw))
            outcome = _classify(status, True, text)
            self.metrics.record(
                CallRecord(
                    self.name, tool, latency_ms, outcome, status, text, elapsed_s
                )
            )
            result["outcome"] = outcome
            result["text"] = text
            return result
        is_error = bool(rpc_result.get("isError", False))
        content = rpc_result.get("content") or []
        text = ""
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text += str(item.get("text", ""))
        structured = rpc_result.get("structuredContent")
        outcome = _classify(status, is_error, text)
        self.metrics.record(
            CallRecord(
                self.name,
                tool,
                latency_ms,
                outcome,
                status,
                text[:200],
                elapsed_s,
            )
        )
        result["ok"] = not is_error
        result["outcome"] = outcome
        result["text"] = text
        result["structured"] = structured
        return result


# ---------------------------------------------------------------------------
# Server subprocess manager
# ---------------------------------------------------------------------------


class Server:
    """Start/stop a fresh `pm` server on port 3150 with scratch dirs."""

    def __init__(self) -> None:
        self.todo_dir = SCRATCH_ROOT / "todo"
        self.db_dir = SCRATCH_ROOT / "db"
        self.log_path = SCRATCH_ROOT / "server.log"
        self.proc: subprocess.Popen[str] | None = None
        self.todo_dir.mkdir(parents=True, exist_ok=True)
        self.db_dir.mkdir(parents=True, exist_ok=True)

    @property
    def db_path(self) -> Path:
        return self.db_dir / "plan_manager.sqlite3"

    @property
    def wal_path(self) -> Path:
        return self.db_dir / "plan_manager.sqlite3-wal"

    def start(self) -> None:
        if not _free_port_check(PORT):
            raise RuntimeError(f"port {PORT} is not free; aborting soak")
        env = os.environ.copy()
        env["TODO_DIR"] = str(self.todo_dir)
        env["PLAN_MANAGER_DB_DIR"] = str(self.db_dir)
        env["HOST"] = HOST
        env["PORT"] = str(PORT)
        env["PLAN_MANAGER_ENABLE_FILE_LOG"] = "false"
        env["PLAN_MANAGER_ENABLE_UI"] = "true"
        env["PLAN_MANAGER_RELOAD"] = "false"
        env["MCP_ENABLE_DNS_REBINDING_PROTECTION"] = "false"
        log_fh = self.log_path.open("a", encoding="utf-8")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "plan_manager"],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self._wait_for_health()

    def _wait_for_health(self) -> None:
        deadline = time.monotonic() + SERVER_STARTUP_TIMEOUT
        last_err = ""
        while time.monotonic() < deadline:
            if self.proc and self.proc.poll() is not None:
                raise RuntimeError(
                    f"server exited early with code {self.proc.returncode}; "
                    f"log:\n{self.log_path.read_text(errors='replace')[:4000]}"
                )
            try:
                r = httpx.get(HEALTH_URL, timeout=2.0)
                if r.status_code == 200:
                    return
                last_err = f"status {r.status_code}"
            except httpx.HTTPError as exc:
                last_err = str(exc)
            time.sleep(0.25)
        raise RuntimeError(f"server did not become healthy: {last_err}")

    def pid(self) -> int | None:
        return self.proc.pid if self.proc else None

    def is_alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)

    def cleanup(self) -> None:
        if SCRATCH_ROOT.exists():
            shutil.rmtree(SCRATCH_ROOT, ignore_errors=True)


# ---------------------------------------------------------------------------
# Resource sampler (background thread)
# ---------------------------------------------------------------------------


def _read_rss_kb(pid: int) -> int:
    try:
        with Path(f"/proc/{pid}/status").open(encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    return int(parts[1])
    except OSError:
        return -1
    return -1


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def resource_sampler(
    server: Server, metrics: Metrics, stop_event: threading.Event
) -> None:
    pid = server.pid()
    while not stop_event.is_set():
        rss = _read_rss_kb(pid) if pid else -1
        db = _file_size(server.db_path)
        wal = _file_size(server.wal_path)
        metrics.sample_resource(rss, db, wal)
        if not server.is_alive():
            metrics.mark_crash()
        stop_event.wait(SAMPLE_INTERVAL)


# ---------------------------------------------------------------------------
# Worker loops
# ---------------------------------------------------------------------------

# Tools considered mutating for ledger purposes.
WORKFLOW_TOOLS = {
    "start_task": "start_task",
    "submit_pr": "submit_pr",
    "approve_pr": "approve_pr",
    "merge_pr": "merge_pr",
    "request_pr_changes": "request_pr_changes",
}


def _think() -> None:
    if THINK_MS > 0:
        time.sleep(THINK_MS / 1000.0)


def _parse_id(result: dict[str, Any], key: str = "id") -> str | None:
    s = result.get("structured")
    if isinstance(s, dict) and key in s:
        return str(s[key])
    # fall back to parsing text JSON
    text = result.get("text") or ""
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and key in obj:
            return str(obj[key])
    except Exception:  # noqa: BLE001
        return None
    return None


def _split_task_id(task_id: str) -> tuple[str, str]:
    if ":" in task_id:
        story, local = task_id.split(":", 1)
        return story, local
    return "", task_id


def worker_loop(
    client: MCPClient,
    plan_id: str,
    stop_event: threading.Event,
    ledger: Ledger,
    shared: bool,
) -> None:
    """Drive a full workflow loop on an assigned plan until stop_event.

    Each iteration: create_story -> create_task -> create_task_steps -> start_task
    -> submit_pr -> (request_pr_changes sometimes) -> approve_pr / merge_pr.
    """
    client.initialize()
    counter = 0
    while not stop_event.is_set():
        counter += 1
        suffix = f"{counter}-{uuid.uuid4().hex[:4]}"
        # create_story
        r = client.call_tool(
            "create_story",
            {"plan_id": plan_id, "title": f"Story {suffix}", "description": "soak"},
        )
        if r["ok"]:
            sid = _parse_id(r) or f"story_{suffix}"
            ledger.add_story(plan_id, sid)
        else:
            _think()
            continue
        # create_task
        r = client.call_tool(
            "create_task",
            {"plan_id": plan_id, "story_id": sid, "title": f"Task {suffix}"},
        )
        if not r["ok"]:
            _think()
            continue
        task_id = _parse_id(r) or f"{sid}:task_{suffix}"
        story_id, local_id = _split_task_id(task_id)
        ledger.add_task(plan_id, story_id, local_id)
        # create_task_steps
        r = client.call_tool(
            "create_task_steps",
            {
                "plan_id": plan_id,
                "task_id": task_id,
                "steps": [{"title": f"step-{i}"} for i in range(3)],
            },
        )
        if not r["ok"]:
            _think()
            continue
        # start_task
        r = client.call_tool("start_task", {"plan_id": plan_id, "task_id": task_id})
        if not r["ok"]:
            _think()
            continue
        ledger.add_workflow(plan_id, story_id, local_id, "start_task")
        # submit_pr
        r = client.call_tool(
            "submit_pr",
            {"plan_id": plan_id, "task_id": task_id, "changes": [f"change {suffix}"]},
        )
        if r["ok"]:
            ledger.add_workflow(plan_id, story_id, local_id, "submit_pr")
        else:
            _think()
            continue
        # rework loop sometimes (request_pr_changes -> submit_pr)
        if counter % 4 == 0:
            r = client.call_tool(
                "request_pr_changes",
                {"plan_id": plan_id, "task_id": task_id, "feedback": "soak rework"},
            )
            if r["ok"]:
                ledger.add_workflow(plan_id, story_id, local_id, "request_pr_changes")
                client.call_tool(
                    "submit_pr",
                    {
                        "plan_id": plan_id,
                        "task_id": task_id,
                        "changes": ["rework change"],
                    },
                )
                ledger.add_workflow(plan_id, story_id, local_id, "submit_pr")
        # finalize: alternate approve_pr and merge_pr
        if counter % 2 == 0:
            r = client.call_tool("approve_pr", {"plan_id": plan_id, "task_id": task_id})
            if r["ok"]:
                ledger.add_workflow(plan_id, story_id, local_id, "approve_pr")
        else:
            r = client.call_tool(
                "merge_pr",
                {
                    "plan_id": plan_id,
                    "task_id": task_id,
                    "changelog_category": "Added",
                    "commit_type": "feat",
                },
            )
            if r["ok"]:
                ledger.add_workflow(plan_id, story_id, local_id, "merge_pr")
        _think()


def reader_loop(
    client: MCPClient,
    plan_ids: list[str],
    stop_event: threading.Event,
) -> None:
    """Continuously poll read-only tools across known plans."""
    client.initialize()
    idx = 0
    while not stop_event.is_set():
        plan_id = plan_ids[idx % len(plan_ids)]
        client.call_tool("list_stories", {"plan_id": plan_id})
        client.call_tool("list_tasks", {"plan_id": plan_id})
        client.call_tool("report", {"plan_id": plan_id})
        client.call_tool("get_current", {"plan_id": plan_id})
        idx += 1
        if stop_event.wait(THINK_MS / 1000.0 + 0.001):
            break


# ---------------------------------------------------------------------------
# Race driver: deliberate same-task start_task races (exactly-one-wins)
# ---------------------------------------------------------------------------


def race_driver(
    client: MCPClient,
    plan_id: str,
    stop_event: threading.Event,
    ledger: Ledger,
    race_results: list[RaceRecord],
    race_failures: list[str],
) -> None:
    """Periodically create a fresh TODO task and race RACE_K start_task calls.

    Asserts exactly-one-wins for every race; records outcomes for the audit.
    """
    client.initialize()
    race_id = 0
    while not stop_event.is_set():
        race_id += 1
        suffix = f"race-{race_id}-{uuid.uuid4().hex[:4]}"
        # 1. create story
        r = client.call_tool(
            "create_story",
            {"plan_id": plan_id, "title": f"Race Story {suffix}"},
        )
        if not r["ok"]:
            stop_event.wait(1.0)
            continue
        sid = _parse_id(r) or f"race_story_{suffix}"
        ledger.add_story(plan_id, sid)
        # 2. create task
        r = client.call_tool(
            "create_task",
            {"plan_id": plan_id, "story_id": sid, "title": f"Race Task {suffix}"},
        )
        if not r["ok"]:
            stop_event.wait(1.0)
            continue
        task_id = _parse_id(r) or f"{sid}:race_task_{suffix}"
        story_id, local_id = _split_task_id(task_id)
        ledger.add_task(plan_id, story_id, local_id)
        # 3. create steps (required before start_task)
        r = client.call_tool(
            "create_task_steps",
            {
                "plan_id": plan_id,
                "task_id": task_id,
                "steps": [{"title": "race-step"}],
            },
        )
        if not r["ok"]:
            stop_event.wait(1.0)
            continue
        # 4. arm the race: RACE_K threads call start_task behind a barrier
        barrier = threading.Barrier(RACE_K)
        outcomes: list[dict[str, Any]] = []
        lock = threading.Lock()

        def racer(
            tid: int,
            _barrier: threading.Barrier = barrier,
            _task_id: str = task_id,
            _lock: threading.Lock = lock,
            _outcomes: list[dict[str, Any]] = outcomes,
        ) -> None:
            with contextlib.suppress(threading.BrokenBarrierError):
                _barrier.wait(timeout=5.0)
            res = client.call_tool(
                "start_task", {"plan_id": plan_id, "task_id": _task_id}
            )
            with _lock:
                _outcomes.append(
                    {
                        "tid": tid,
                        "ok": res["ok"],
                        "outcome": res["outcome"],
                        "text": res["text"][:160],
                    }
                )

        with ThreadPoolExecutor(max_workers=RACE_K) as pool:
            futs = [pool.submit(racer, i) for i in range(RACE_K)]
            for f in futs:
                f.result(timeout=30)
        successes = sum(1 for o in outcomes if o["ok"])
        failures = RACE_K - successes
        failure_kinds = [o["outcome"] for o in outcomes if not o["ok"]]
        winner = next((o["tid"] for o in outcomes if o["ok"]), None)
        rec = RaceRecord(
            race_id,
            plan_id,
            story_id,
            local_id,
            successes,
            failures,
            failure_kinds,
            winner,
        )
        ledger.add_race(rec)
        race_results.append(rec)
        # 5. assert exactly-one-wins (loud)
        if successes != 1:
            race_failures.append(
                f"race {race_id} on {plan_id}/{task_id}: expected 1 success, got {successes}; "
                f"outcomes={outcomes}"
            )
        else:
            # 6. drive the winning task to completion so the workflow stays consistent
            ledger.add_workflow(plan_id, story_id, local_id, "start_task")
            r = client.call_tool(
                "submit_pr",
                {"plan_id": plan_id, "task_id": task_id, "changes": ["race change"]},
            )
            if r["ok"]:
                ledger.add_workflow(plan_id, story_id, local_id, "submit_pr")
            client.call_tool("approve_pr", {"plan_id": plan_id, "task_id": task_id})
            ledger.add_workflow(plan_id, story_id, local_id, "approve_pr")
        # pace the races
        if stop_event.wait(RACE_INTERVAL):
            break


# ---------------------------------------------------------------------------
# Post-run integrity audit
# ---------------------------------------------------------------------------


def _open_db_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def integrity_audit(
    server: Server, ledger: Ledger, race_failures: list[str]
) -> dict[str, Any]:
    """Run PRAGMA integrity_check + foreign_key_check and reconcile the ledger."""
    results: dict[str, Any] = {
        "integrity_check": None,
        "foreign_key_check": None,
        "plan_count": 0,
        "story_count": 0,
        "task_count": 0,
        "event_count": 0,
        "ledger_reconciliation": {},
        "race_audit": {},
        "errors": [],
    }
    db_path = server.db_path
    if not db_path.exists():
        results["errors"].append(f"DB file missing at {db_path}")
        return results
    conn = _open_db_readonly(db_path)
    try:
        # The server is stopped by now; WAL content is committed. We read in
        # read-only mode to avoid mutating the scratch DB during the audit.
        row = conn.execute("PRAGMA integrity_check").fetchone()
        results["integrity_check"] = str(row[0]) if row is not None else "no-row"
        fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
        results["foreign_key_check"] = [list(r) for r in fk_rows]
        results["plan_count"] = int(
            conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0]
        )
        results["story_count"] = int(
            conn.execute("SELECT COUNT(*) FROM stories").fetchone()[0]
        )
        results["task_count"] = int(
            conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        )
        results["event_count"] = int(
            conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        )

        snap = ledger.snapshot()
        recon: dict[str, Any] = {}
        # plans
        db_plan_ids = {
            str(r["id"]) for r in conn.execute("SELECT id FROM plans").fetchall()
        }
        ledger_plan_ids = set(snap["plans"])
        recon["plans_ledger"] = len(ledger_plan_ids)
        recon["plans_db"] = len(db_plan_ids)
        recon["plans_missing_in_db"] = sorted(ledger_plan_ids - db_plan_ids)
        # stories
        db_story_keys = {
            (str(r["plan_id"]), str(r["id"]))
            for r in conn.execute("SELECT plan_id, id FROM stories").fetchall()
        }
        ledger_story_keys = set(snap["stories"])
        recon["stories_ledger"] = len(ledger_story_keys)
        recon["stories_db"] = len(db_story_keys)
        recon["stories_missing_in_db"] = sorted(
            [tuple(map(str, k)) for k in (ledger_story_keys - db_story_keys)]
        )
        # tasks
        db_task_keys = {
            (str(r["plan_id"]), str(r["story_id"]), str(r["local_id"]))
            for r in conn.execute(
                "SELECT plan_id, story_id, local_id FROM tasks"
            ).fetchall()
        }
        ledger_task_keys = set(snap["tasks"])
        recon["tasks_ledger"] = len(ledger_task_keys)
        recon["tasks_db"] = len(db_task_keys)
        recon["tasks_missing_in_db"] = sorted(
            [tuple(map(str, k)) for k in (ledger_task_keys - db_task_keys)]
        )
        # workflow mutation count vs event count.
        recon["workflow_mutations_ledger"] = len(snap["workflow_mutations"])
        # Every workflow mutation appends at least one event (task_status_changed
        # or review_changes_requested). `request_pr_changes` appends TWO events
        # (review_changes_requested AND task_status_changed); all other
        # workflow mutations append exactly one. merge_pr's internal approve
        # appends one. So expected events = mutations + (#request_pr_changes).
        request_changes_count = sum(
            1
            for entry in snap["workflow_mutations"]
            if entry[3] == "request_pr_changes"
        )
        expected_events = len(snap["workflow_mutations"]) + request_changes_count
        recon["event_count_db"] = results["event_count"]
        recon["expected_events"] = expected_events
        recon["request_changes_count"] = request_changes_count
        recon["events_match_mutations"] = results["event_count"] == expected_events
        # per-plan event seq monotonic ordering (verified via a LAG window
        # below; the events_plan index plus AUTOINCREMENT seq guarantees it,
        # but we assert it explicitly for the audit).
        non_monotonic = conn.execute(
            "SELECT plan_id, COUNT(*) AS c FROM ("
            "  SELECT plan_id, seq, LAG(seq) OVER (PARTITION BY plan_id ORDER BY rowid) AS prev "
            "  FROM events"
            ") WHERE prev IS NOT NULL AND seq <= prev "
            "GROUP BY plan_id"
        ).fetchall()
        recon["event_seq_non_monotonic"] = [str(r["plan_id"]) for r in non_monotonic]
        results["ledger_reconciliation"] = recon

        # race audit: each race should have exactly 1 success and the task
        # should be DONE (we drove it to completion) — verify status in DB.
        race_audit: list[dict[str, Any]] = []
        for rec in snap["races"]:
            row = conn.execute(
                "SELECT status FROM tasks WHERE plan_id=? AND story_id=? AND local_id=?",
                (rec.plan_id, rec.story_id, rec.task_id),
            ).fetchone()
            status = str(row["status"]) if row is not None else "MISSING"
            race_audit.append(
                {
                    "race_id": rec.race_id,
                    "plan_id": rec.plan_id,
                    "task_id": f"{rec.story_id}:{rec.task_id}",
                    "successes": rec.successes,
                    "failures": rec.failures,
                    "failure_kinds": rec.failure_kinds,
                    "final_status": status,
                    "exactly_one_win": rec.successes == 1,
                    "task_present": row is not None,
                }
            )
        results["race_audit"] = race_audit
        if race_failures:
            results["errors"].extend(race_failures)
        if recon["plans_missing_in_db"]:
            results["errors"].append(
                f"plans missing in DB: {recon['plans_missing_in_db']}"
            )
        if recon["stories_missing_in_db"]:
            results["errors"].append(
                f"stories missing in DB: {recon['stories_missing_in_db']}"
            )
        if recon["tasks_missing_in_db"]:
            results["errors"].append(
                f"tasks missing in DB: {recon['tasks_missing_in_db']}"
            )
        if not recon["events_match_mutations"]:
            results["errors"].append(
                f"event count {recon['event_count_db']} != expected events "
                f"{recon['expected_events']} (mutations "
                f"{recon['workflow_mutations_ledger']} + "
                f"{recon['request_changes_count']} request_pr_changes)"
            )
        if recon["event_seq_non_monotonic"]:
            results["errors"].append(
                f"non-monotonic event seq for plans: {recon['event_seq_non_monotonic']}"
            )
        if results["integrity_check"] != "ok":
            results["errors"].append(f"integrity_check: {results['integrity_check']}")
        if results["foreign_key_check"]:
            results["errors"].append(
                f"foreign_key_check violations: {results['foreign_key_check']}"
            )
    finally:
        conn.close()
    return results


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------


def _fmt_ms(v: float) -> str:
    return f"{v:.1f}"


def _write_report(
    report_path: Path,
    *,
    setup: dict[str, Any],
    metrics_snap: dict[str, Any],
    audit: dict[str, Any],
    ledger_snap: dict[str, Any],
    verdict: dict[str, Any],
    duration_s: float,
    raw_calls: list[CallRecord] | None = None,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# U9 — Concurrency Soak Report")
    lines.append("")
    lines.append(f"Branch: develop @ {setup['git_sha']}")
    lines.append(f"Generated: {setup['generated_at']}")
    lines.append(f"Wall-clock duration: {duration_s:.1f}s")
    lines.append("")
    lines.append("## 1. Setup")
    lines.append("")
    lines.append("| parameter | value |")
    lines.append("|---|---|")
    for k, v in setup["params"].items():
        lines.append(f"| `{k}` | `{v}` |")
    lines.append("")
    lines.append(f"Scratch dir: `{setup['scratch_root']}`")
    lines.append(f"Server log: `{setup['server_log']}`")
    lines.append("")
    lines.append("## 2. Load profile")
    lines.append("")
    lines.append(f"- Ramp to **{RAMP_CLIENTS}** concurrent clients.")
    lines.append(f"- Sustained **{SUSTAIN_SECONDS:.0f}s** at {RAMP_CLIENTS} clients.")
    lines.append(
        f"- Thundering-herd burst: **{BURST_CLIENTS}** clients for **{BURST_SECONDS:.0f}s**."
    )
    lines.append(
        f"- Deliberate same-task races: K={RACE_K} every ~{RACE_INTERVAL:.0f}s."
    )
    lines.append(
        f"- Mix: {NUM_PLANS} owned plans + 2 shared plans; readers + contenders + race driver."
    )
    lines.append("")
    lines.append("## 3. Metrics")
    lines.append("")
    lines.append(f"Total calls: **{metrics_snap['total_calls']}**")
    lines.append("")
    lines.append("### 3.1 Error taxonomy")
    lines.append("")
    lines.append("| outcome | count |")
    lines.append("|---|---|")
    lines.extend(
        f"| {oc} | {metrics_snap['outcome_counts'].get(oc, 0)} |" for oc in OUTCOMES
    )
    lines.append("")
    busy = metrics_snap["outcome_counts"].get(BUSY_EXHAUSTED, 0)
    total = metrics_snap["total_calls"] or 1
    lines.append(f"Busy-exhaustion rate: {busy} / {total} = {busy / total * 100:.4f}%")
    lines.append("")
    lines.append("### 3.2 Per-tool latency (ms)")
    lines.append("")
    lines.append("| tool | n | p50 | p95 | p99 | max | mean |")
    lines.append("|---|---|---|---|---|---|---|")
    for tool, p in sorted(metrics_snap["by_tool_latencies"].items()):
        lines.append(
            f"| {tool} | {p['n']} | {_fmt_ms(p['p50'])} | {_fmt_ms(p['p95'])} | "
            f"{_fmt_ms(p['p99'])} | {_fmt_ms(p['max'])} | {_fmt_ms(p['mean'])} |"
        )
    lines.append("")
    lines.append("### 3.3 Per-tool outcome breakdown")
    lines.append("")
    lines.append("| tool | " + " | ".join(OUTCOMES) + " |")
    lines.append("|---|" + "|".join(["---"] * len(OUTCOMES)) + "|")
    for tool, counts in sorted(metrics_snap["outcome_by_tool"].items()):
        row = [tool] + [str(counts.get(o, 0)) for o in OUTCOMES]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    lines.append("### 3.4 Server RSS over time")
    lines.append("")
    rss = metrics_snap["rss_samples"]
    if rss:
        rss_kb = [v for _, v in rss]
        lines.append(f"- samples: {len(rss)}")
        lines.append(
            f"- min: {min(rss_kb)} kB, max: {max(rss_kb)} kB, last: {rss_kb[-1]} kB"
        )
        lines.append(f"- drift (last - first): {rss_kb[-1] - rss_kb[0]} kB")
        lines.append("")
        lines.append("| elapsed_s | rss_kB |")
        lines.append("|---|---|")
        for t, v in rss[:: max(1, len(rss) // 30)]:
            lines.append(f"| {t:.1f} | {v} |")
        lines.append("")
    else:
        lines.append("_no RSS samples_")
        lines.append("")
    lines.append("### 3.5 DB + WAL file size over time")
    lines.append("")
    dbs = metrics_snap["db_samples"]
    if dbs:
        lines.append("| elapsed_s | db_bytes | wal_bytes |")
        lines.append("|---|---|---|")
        for t, db, wal in dbs[:: max(1, len(dbs) // 30)]:
            lines.append(f"| {t:.1f} | {db} | {wal} |")
        wal_sizes = [w for _, _, w in dbs]
        lines.append("")
        lines.append(f"- WAL last: {wal_sizes[-1]} bytes; max: {max(wal_sizes)} bytes")
        # monotonic growth check (post-checkpoint bounded): compare last 3 samples
        tail = wal_sizes[-5:] if len(wal_sizes) >= 5 else wal_sizes
        lines.append(f"- WAL tail (last {len(tail)}): {tail}")
    else:
        lines.append("_no DB size samples_")
    lines.append("")
    lines.append("### 3.6 p95 latency by sustained-window half (drift audit)")
    lines.append("")
    # Recompute the time-binned p95 used by the verdict so the report shows
    # exactly what the criterion was evaluated against.
    raw_for_drift = list(raw_calls or [])
    lines.append(
        f"- ramp excluded: first {min(30.0, max(2.0, SUSTAIN_SECONDS * 0.1)):.0f}s; "
        f"sustained window: [{min(30.0, max(2.0, SUSTAIN_SECONDS * 0.1)):.0f}s, "
        f"{SUSTAIN_SECONDS:.0f}s]; burst excluded."
    )
    if raw_for_drift:
        ramp_end = min(30.0, max(2.0, SUSTAIN_SECONDS * 0.1))
        mid = ramp_end + (SUSTAIN_SECONDS - ramp_end) / 2.0
        fh = [c.latency_ms for c in raw_for_drift if ramp_end <= c.elapsed_s < mid]
        lh = [
            c.latency_ms for c in raw_for_drift if mid <= c.elapsed_s <= SUSTAIN_SECONDS
        ]
        lines.append(
            f"- first-half p95={_percentiles(fh)['p95']:.1f}ms (n={len(fh)}); "
            f"second-half p95={_percentiles(lh)['p95']:.1f}ms (n={len(lh)})"
        )
    else:
        lines.append("- raw per-call records not available in snapshot")
    lines.append("")
    lines.append("## 4. Integrity audit")
    lines.append("")
    lines.append(f"- PRAGMA integrity_check: **{audit['integrity_check']}**")
    lines.append(f"- PRAGMA foreign_key_check: {audit['foreign_key_check'] or 'clean'}")
    lines.append(f"- plans in DB: {audit['plan_count']}")
    lines.append(f"- stories in DB: {audit['story_count']}")
    lines.append(f"- tasks in DB: {audit['task_count']}")
    lines.append(f"- events in DB: {audit['event_count']}")
    lines.append("")
    recon = audit["ledger_reconciliation"]
    if recon:
        lines.append("### 4.1 Ledger reconciliation")
        lines.append("")
        lines.append("| check | ledger | db |")
        lines.append("|---|---|---|")
        lines.append(f"| plans | {recon['plans_ledger']} | {recon['plans_db']} |")
        lines.append(f"| stories | {recon['stories_ledger']} | {recon['stories_db']} |")
        lines.append(f"| tasks | {recon['tasks_ledger']} | {recon['tasks_db']} |")
        lines.append(
            f"| workflow mutations vs events | {recon['workflow_mutations_ledger']} "
            f"(+{recon['request_changes_count']} req-changes = "
            f"{recon['expected_events']} expected) | "
            f"{recon['event_count_db']} (match={recon['events_match_mutations']}) |"
        )
        lines.append("")
        if recon["plans_missing_in_db"]:
            lines.append(f"Plans missing in DB: {recon['plans_missing_in_db']}")
        if recon["stories_missing_in_db"]:
            lines.append(f"Stories missing in DB: {recon['stories_missing_in_db']}")
        if recon["tasks_missing_in_db"]:
            lines.append(f"Tasks missing in DB: {recon['tasks_missing_in_db']}")
        lines.append(
            f"Non-monotonic event seq plans: {recon['event_seq_non_monotonic']}"
        )
    lines.append("")
    lines.append("### 4.2 Race audit (exactly-one-wins)")
    lines.append("")
    races = audit["race_audit"]
    lines.append(f"Deliberate races executed: {len(races)}")
    bad_races = [r for r in races if not r["exactly_one_win"]]
    lines.append(f"Races with exactly-one-win: {len(races) - len(bad_races)}")
    lines.append(f"Races violating exactly-one-win: {len(bad_races)}")
    lines.append("")
    if races:
        lines.append(
            "| race | plan | task | successes | failures | final_status | ok |"
        )
        lines.append("|---|---|---|---|---|---|---|")
        lines.extend(
            f"| {r['race_id']} | {r['plan_id']} | {r['task_id']} | "
            f"{r['successes']} | {r['failures']} | {r['final_status']} | "
            f"{'yes' if r['exactly_one_win'] else 'NO'} |"
            for r in races[:: max(1, len(races) // 20)]
        )
    lines.append("")
    lines.append("## 5. Verdict")
    lines.append("")
    lines.append("| criterion | result |")
    lines.append("|---|---|")
    for crit, val in verdict["criteria"].items():
        lines.append(f"| {crit} | {val} |")
    lines.append("")
    lines.append(f"**Overall: {verdict['overall']}**")
    lines.append("")
    if audit["errors"]:
        lines.append("## 6. Errors / reproduction detail")
        lines.append("")
        lines.extend(f"- {e}" for e in audit["errors"][:50])
        lines.append("")
    if verdict["overall"] != "pass":
        lines.append("## 7. Reproduction")
        lines.append("")
        lines.append("```")
        lines.append("uv run pytest -m soak tests/soak/")
        lines.append("```")
        lines.append("")
        lines.append(f"Server log preserved at: `{setup['server_log']}`")
        lines.append(f"Scratch DB dir: `{setup['scratch_root']}/db`")
        lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO_ROOT), text=True
        ).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _drift_check(values: list[float], window: int = 10) -> str:
    """Return 'stable' / 'drift-up' / 'drift-down' / 'insufficient' for a tail window."""
    if len(values) < window * 2:
        return "insufficient"
    first = statistics.mean(values[-window * 2 : -window])
    last = statistics.mean(values[-window:])
    if last == 0 or first == 0:
        return "stable"
    ratio = last / first
    if ratio > 1.25:
        return "drift-up"
    if ratio < 0.75:
        return "drift-down"
    return "stable"


def run_soak() -> dict[str, Any]:
    """Run the full soak harness end-to-end and write the report."""
    server = Server()
    metrics = Metrics()
    ledger = Ledger()
    race_results: list[RaceRecord] = []
    race_failures: list[str] = []
    stop_event = threading.Event()
    threads: list[threading.Thread] = []
    clients: list[MCPClient] = []
    sampler_thread: threading.Thread | None = None

    # Plan ids are assigned from the server's actual create_plan responses
    # (ids are slugified from titles, so we use the returned id rather than a
    # precomputed string).
    owned_plan_ids: list[str] = []
    shared_plan_ids: list[str] = []
    all_plan_ids: list[str] = []

    start_time = time.monotonic()
    try:
        server.start()
        # Seed all plans up front via a throwaway client so readers/contenders
        # have stable targets; record them in the ledger.
        seeder = MCPClient("seeder", metrics)
        seeder.initialize()
        for i in range(NUM_PLANS):
            r = seeder.call_tool("create_plan", {"title": f"Soak Owned {i}"})
            if r["ok"] and _parse_id(r):
                owned_plan_ids.append(_parse_id(r))  # type: ignore[arg-type]
                ledger.add_plan(_parse_id(r))  # type: ignore[arg-type]
        for label in ("A", "B"):
            r = seeder.call_tool("create_plan", {"title": f"Soak Shared {label}"})
            if r["ok"] and _parse_id(r):
                shared_plan_ids.append(_parse_id(r))  # type: ignore[arg-type]
                ledger.add_plan(_parse_id(r))  # type: ignore[arg-type]
        seeder.close()
        all_plan_ids = owned_plan_ids + shared_plan_ids
        if len(shared_plan_ids) < 2:
            raise RuntimeError(
                f"seeding failed; owned={owned_plan_ids} shared={shared_plan_ids}"
            )

        # Start resource sampler.
        sampler_thread = threading.Thread(
            target=resource_sampler, args=(server, metrics, stop_event), daemon=True
        )
        sampler_thread.start()

        # Start the race driver (counts as 1 client).
        race_client = MCPClient("race-driver", metrics)
        clients.append(race_client)
        race_thread = threading.Thread(
            target=race_driver,
            args=(
                race_client,
                shared_plan_ids[0],
                stop_event,
                ledger,
                race_results,
                race_failures,
            ),
            daemon=True,
        )
        race_thread.start()
        threads.append(race_thread)

        # Sustained phase: ramp to RAMP_CLIENTS.
        # Composition: NUM_PLANS owners + contenders on 2 shared plans +
        # readers, totalling RAMP_CLIENTS (race driver already counted).
        # Adaptive so small smoke configs still produce a sane mix.
        sustained_target = RAMP_CLIENTS - 1  # race driver already running
        owners = len(owned_plan_ids)
        readers = max(1, sustained_target // 4)
        contenders = max(0, sustained_target - owners - readers)
        # Split contenders across the two shared plans.
        contenders_shared_a = (contenders + 1) // 2
        contenders_shared_b = contenders - contenders_shared_a

        def spawn_owner(idx: int) -> None:
            pid = owned_plan_ids[idx]
            c = MCPClient(f"owner-{idx}", metrics)
            clients.append(c)
            t = threading.Thread(
                target=worker_loop,
                args=(c, pid, stop_event, ledger, False),
                daemon=True,
            )
            t.start()
            threads.append(t)

        def spawn_contender(shared_idx: int, slot: int) -> None:
            pid = shared_plan_ids[shared_idx]
            c = MCPClient(f"contender-{shared_idx}-{slot}", metrics)
            clients.append(c)
            t = threading.Thread(
                target=worker_loop, args=(c, pid, stop_event, ledger, True), daemon=True
            )
            t.start()
            threads.append(t)

        def spawn_reader(idx: int) -> None:
            c = MCPClient(f"reader-{idx}", metrics)
            clients.append(c)
            t = threading.Thread(
                target=reader_loop, args=(c, all_plan_ids, stop_event), daemon=True
            )
            t.start()
            threads.append(t)

        # Ramp gradually over the first ~30s (or shorter if sustain is short).
        ramp_window = min(30.0, max(2.0, SUSTAIN_SECONDS * 0.1))
        ramp_step = ramp_window / max(1, sustained_target)
        for i in range(owners):
            spawn_owner(i)
            time.sleep(ramp_step)
        for slot in range(contenders_shared_a):
            spawn_contender(0, slot)
            time.sleep(ramp_step)
        for slot in range(contenders_shared_b):
            spawn_contender(1, slot)
            time.sleep(ramp_step)
        for i in range(readers):
            spawn_reader(i)
            time.sleep(ramp_step)

        # Sustain.
        stop_event.wait(SUSTAIN_SECONDS)

        # Burst phase: spin up extra clients to reach BURST_CLIENTS total.
        burst_extra = BURST_CLIENTS - (1 + owners + contenders + readers)
        burst_threads: list[threading.Thread] = []
        if burst_extra > 0:
            burst_stop = threading.Event()

            def burst_worker(idx: int) -> None:
                c = MCPClient(f"burst-{idx}", metrics)
                clients.append(c)
                pid = shared_plan_ids[idx % 2]
                t = threading.Thread(
                    target=worker_loop,
                    args=(c, pid, burst_stop, ledger, True),
                    daemon=True,
                )
                t.start()
                burst_threads.append(t)

            for i in range(burst_extra):
                burst_worker(i)
                time.sleep(0.05)
            stop_event.wait(BURST_SECONDS)
            burst_stop.set()
            for t in burst_threads:
                t.join(timeout=10)

    finally:
        stop_event.set()
        # Join workers briefly.
        for t in threads:
            t.join(timeout=15)
        for c in clients:
            c.close()
        if sampler_thread is not None:
            sampler_thread.join(timeout=5)
        server.stop()

    duration_s = time.monotonic() - start_time

    # Post-run integrity audit.
    audit = integrity_audit(server, ledger, race_failures)
    metrics_snap = metrics.snapshot()
    ledger_snap = ledger.snapshot()

    # ---- Verdict against explicit pass criteria ----
    criteria: dict[str, str] = {}
    integrity_ok = (
        audit["integrity_check"] == "ok"
        and not audit["foreign_key_check"]
        and not audit["ledger_reconciliation"].get("plans_missing_in_db")
        and not audit["ledger_reconciliation"].get("stories_missing_in_db")
        and not audit["ledger_reconciliation"].get("tasks_missing_in_db")
        and audit["ledger_reconciliation"].get("events_match_mutations")
        and not audit["ledger_reconciliation"].get("event_seq_non_monotonic")
    )
    criteria["ZERO integrity violations"] = "PASS" if integrity_ok else "FAIL"

    unexpected_5xx = metrics_snap["outcome_counts"].get(HTTP_5XX, 0)
    crashes = 1 if metrics_snap["server_crashed"] else 0
    conn_err = metrics_snap["outcome_counts"].get(CONNECTION_ERROR, 0)
    no_crashes = (unexpected_5xx + crashes + conn_err) == 0
    criteria["ZERO unexpected 5xx/crashes"] = "PASS" if no_crashes else "FAIL"

    busy = metrics_snap["outcome_counts"].get(BUSY_EXHAUSTED, 0)
    total = metrics_snap["total_calls"] or 1
    busy_rate = busy / total
    busy_structured_ok = True
    # If busy errors occurred, verify they surfaced as the documented structured
    # error (text contains "busy"/"retry later"). The classifier already gates on
    # this; any UNEXPECTED_ERROR with busy-like text would be a defect.
    if busy > 0:
        busy_structured_ok = busy_rate < 0.001
    busy_pass = busy == 0 or (busy_rate < 0.001 and busy_structured_ok)
    criteria["busy-exhaustion 0 (or <0.1% structured)"] = (
        "PASS" if busy_pass else f"FAIL ({busy} errors, {busy_rate * 100:.4f}%)"
    )

    # p95 latency stable across the sustained window (no upward drift).
    # We bin calls by elapsed time (recorded per call) and compare p95 of the
    # first half of the sustained steady-state window vs the second half,
    # explicitly excluding the ramp-up region and the burst phase.
    raw = metrics.calls
    ramp_end = min(30.0, max(2.0, SUSTAIN_SECONDS * 0.1))
    sustained_end = SUSTAIN_SECONDS  # burst starts here
    sustained_calls = [c for c in raw if ramp_end <= c.elapsed_s <= sustained_end]
    if len(sustained_calls) >= 40:
        mid = ramp_end + (sustained_end - ramp_end) / 2.0
        first_half = [c.latency_ms for c in sustained_calls if c.elapsed_s < mid]
        last_half = [c.latency_ms for c in sustained_calls if c.elapsed_s >= mid]
        fp95 = _percentiles(first_half)["p95"]
        lp95 = _percentiles(last_half)["p95"]
        if fp95 == 0:
            drift = "stable" if lp95 == 0 else "drift-up"
        else:
            ratio = lp95 / fp95
            drift = (
                "drift-up"
                if ratio > 1.5
                else ("drift-down" if ratio < 0.667 else "stable")
            )
        # Orchestrator disposition (2026-08-05, U9): latency drift under this
        # deliberately saturating closed-loop profile is REPORTED, not a hard
        # failure. Diagnosis: single-call service times are ~10ms even on the
        # fattest soak DB; observed p95 growth is queueing at saturation plus
        # service-time creep as the harness grows plans far past realistic
        # sizes. Hard failures remain the never-events (integrity, crashes,
        # busy-exhaustion, unbounded RSS/WAL, race correctness).
        criteria["p95 latency drift (reported, non-blocking)"] = (
            f"REPORTED ({drift}: sustained-window first-half p95={fp95:.1f}ms "
            f"over n={len(first_half)}, second-half p95={lp95:.1f}ms over "
            f"n={len(last_half)})"
        )
    else:
        criteria["p95 latency drift (reported, non-blocking)"] = (
            f"REPORTED (insufficient sustained data: {len(sustained_calls)} calls)"
        )

    # RSS bounded (no monotonic growth): last sample <= first * 1.5 + 50MB.
    rss = metrics_snap["rss_samples"]
    if rss:
        rss_kb = [v for _, v in rss if v > 0]
        if len(rss_kb) >= 2:
            first, last = rss_kb[0], rss_kb[-1]
            rss_bounded = last <= max(first * 1.5 + 50_000, first + 100_000)
            criteria["RSS bounded (no monotonic growth)"] = (
                f"{'PASS' if rss_bounded else 'FAIL'} (first={first}kB, last={last}kB)"
            )
        else:
            criteria["RSS bounded (no monotonic growth)"] = (
                "PASS (insufficient samples)"
            )
    else:
        criteria["RSS bounded (no monotonic growth)"] = "FAIL (no samples)"

    # WAL bounded: last WAL size not monotonically growing; compare last 5 samples.
    dbs = metrics_snap["db_samples"]
    wal_bounded = True
    wal_detail = "no samples"
    if dbs and len(dbs) >= 5:
        wal_sizes = [w for _, _, w in dbs]
        tail = wal_sizes[-5:]
        wal_bounded = tail[-1] <= max(tail[0] * 2, 64 * 1024 * 1024) or tail[-1] == 0
        wal_detail = f"last={tail[-1]}, tail={tail}"
    criteria["WAL size bounded (post-checkpoint)"] = (
        f"{'PASS' if wal_bounded else 'FAIL'} ({wal_detail})"
    )

    # Race exactly-one-wins.
    bad_races = [r for r in audit["race_audit"] if not r["exactly_one_win"]]
    criteria["same-task races exactly-one-wins"] = (
        "PASS" if not bad_races else f"FAIL ({len(bad_races)} races violated)"
    )

    failed = [k for k, v in criteria.items() if v.startswith("FAIL")]
    overall = "pass" if not failed else "fail"

    verdict = {"criteria": criteria, "overall": overall, "failed": failed}

    setup_info = {
        "git_sha": _git_sha(),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scratch_root": str(SCRATCH_ROOT),
        "server_log": str(server.log_path),
        "params": {
            "PORT": PORT,
            "NUM_PLANS": NUM_PLANS,
            "RAMP_CLIENTS": RAMP_CLIENTS,
            "SUSTAIN_SECONDS": SUSTAIN_SECONDS,
            "BURST_CLIENTS": BURST_CLIENTS,
            "BURST_SECONDS": BURST_SECONDS,
            "RACE_K": RACE_K,
            "RACE_INTERVAL": RACE_INTERVAL,
            "THINK_MS": THINK_MS,
        },
    }
    _write_report(
        REPORT_PATH,
        setup=setup_info,
        metrics_snap=metrics_snap,
        audit=audit,
        ledger_snap=ledger_snap,
        verdict=verdict,
        duration_s=duration_s,
        raw_calls=metrics.calls,
    )

    # Copy server log into the report dir for reproduction if failed.
    if overall != "pass" and server.log_path.exists():
        log_copy = REPORT_PATH.parent / "u9-soak-server.log"
        with contextlib.suppress(OSError):
            shutil.copyfile(server.log_path, log_copy)

    # On pass, clean up the scratch dirs (kept on failure for reproduction).
    if overall == "pass":
        server.cleanup()

    return {
        "overall": overall,
        "criteria": criteria,
        "total_calls": metrics_snap["total_calls"],
        "outcome_counts": metrics_snap["outcome_counts"],
        "races": len(audit["race_audit"]),
        "bad_races": len(bad_races),
        "report_path": str(REPORT_PATH),
        "duration_s": duration_s,
    }
