# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev
# ruff: noqa: INP001

"""Verify the exact built wheel from outside the source checkout."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from email.parser import Parser
from pathlib import Path

_TOOL_CONTRACT_SHA256 = (
    "e57260fe9a333439fa36ee9ba60d11bde52559ed60c316846aefe5888023f4fa"
)


def _wheel(dist: Path) -> Path:
    wheels = sorted(dist.glob("plan_manager-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected one Plan Manager wheel, found {wheels}")
    return wheels[0]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    wheel = _wheel(root / "dist")
    expected_revision = os.getenv("PLAN_MANAGER_SOURCE_REVISION") or "unknown"
    expected_guides = {
        "resource://plan-manager/usage_guide_agents.md": (
            root / "docs" / "usage_guide_agents.md"
        ).read_text(),
        "resource://plan-manager/project_workflow.md": (
            root / "docs" / "project_workflow.md"
        ).read_text(),
    }

    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="plan-manager-wheel-") as temp_name:
        temp = Path(temp_name)
        with zipfile.ZipFile(wheel) as archive:
            names = set(archive.namelist())
            required = {
                "plan_manager/docs/usage_guide_agents.md",
                "plan_manager/docs/project_workflow.md",
                "plan_manager/_build_identity.json",
            }
            missing = required - names
            if missing:
                raise RuntimeError(f"wheel members missing: {sorted(missing)}")
            metadata_name = next(
                name
                for name in names
                if name.endswith(".dist-info/METADATA")
                and name.startswith("plan_manager-")
            )
            wheel_version = Parser().parsestr(
                archive.read(metadata_name).decode("utf-8")
            )["Version"]
            archive.extractall(temp)

        probe = r"""
import json
import os
from pathlib import Path
from starlette.testclient import TestClient

from plan_manager.identity import build_identity
from plan_manager.resources.usage_resources import register_usage_resources
from plan_manager.server.app import starlette_app

class FakeMCP:
    def __init__(self):
        self.handlers = {}
    def resource(self, **kwargs):
        def decorate(function):
            self.handlers[kwargs["uri"]] = function
            return function
        return decorate

fake = FakeMCP()
register_usage_resources(fake)
guides = {
    uri: fake.handlers[uri]()
    for uri in (
        "resource://plan-manager/usage_guide_agents.md",
        "resource://plan-manager/project_workflow.md",
    )
}
identity = build_identity()
body = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "artifact-probe", "version": "0"},
    },
}
headers = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}
with TestClient(starlette_app(), base_url="http://127.0.0.1:3000") as client:
    def rpc(request_id, method, params):
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            raise RuntimeError(payload["error"])
        return payload["result"]

    def tool(request_id, name, arguments):
        result = rpc(
            request_id,
            "tools/call",
            {"name": name, "arguments": arguments},
        )
        if result.get("isError"):
            raise RuntimeError(result)
        return result["structuredContent"]

    response = client.post("/mcp", json=body, headers=headers)
    response.raise_for_status()
    initialized = response.json()["result"]
    listed_resources = rpc(2, "resources/list", {})["resources"]
    listed_uris = {item["uri"] for item in listed_resources}
    live_guides = {}
    for request_id, uri in enumerate(guides, start=3):
        content = rpc(request_id, "resources/read", {"uri": uri})["contents"]
        live_guides[uri] = content[0]["text"]
    build_info_text = rpc(
        5,
        "resources/read",
        {"uri": "resource://plan-manager/build_info.json"},
    )["contents"][0]["text"]
    tools = rpc(6, "tools/list", {})["tools"]

    plan = tool(7, "create_plan", {"title": "Artifact Drill"})
    story = tool(
        8,
        "create_story",
        {"plan_id": plan["id"], "title": "Authority Boundary"},
    )
    task = tool(
        9,
        "create_task",
        {
            "plan_id": plan["id"],
            "story_id": story["id"],
            "title": "Continue Authorized Work",
        },
    )
    stepped = tool(
        10,
        "create_task_steps",
        {
            "plan_id": plan["id"],
            "task_id": task["id"],
            "steps": [{"title": "Exercise installed workflow"}],
        },
    )
    started = tool(
        11,
        "start_task",
        {"plan_id": plan["id"], "task_id": task["id"]},
    )
    submitted = tool(
        12,
        "submit_pr",
        {
            "plan_id": plan["id"],
            "task_id": task["id"],
            "changes": ["Exercised installed authority guidance"],
        },
    )
    health = client.get("/health")
    health.raise_for_status()
print(json.dumps({
    "module": str(Path(__import__("plan_manager").__file__).resolve()),
    "guides": guides,
    "live_guides": live_guides,
    "listed_uris": sorted(listed_uris),
    "build_info_resource": json.loads(build_info_text),
    "tool_count": len(tools),
    "tool_contract": {item["name"]: item["inputSchema"] for item in tools},
    "stepped_actions": stepped["next_actions"],
    "started_actions": started["next_actions"],
    "submitted_actions": submitted["next_actions"],
    "identity": identity,
    "server_version": initialized["serverInfo"]["version"],
    "protocol_version": initialized["protocolVersion"],
    "health": health.json(),
}, sort_keys=True))
"""
        env = dict(os.environ)
        env["PYTHONPATH"] = str(temp)
        env["PLAN_MANAGER_DB_DIR"] = str(temp / "db")
        env["TODO_DIR"] = str(temp / "todo")
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=temp,
            env=env,
            check=True,
            text=True,
            capture_output=True,
        )
        json_line = next(
            line
            for line in reversed(result.stdout.splitlines())
            if line.startswith("{")
        )
        observed = json.loads(json_line)
        if not Path(observed["module"]).is_relative_to(temp):
            raise RuntimeError("probe imported Plan Manager outside extracted wheel")
        if observed["guides"] != expected_guides:
            raise RuntimeError("installed guide payloads differ from release documents")
        if observed["live_guides"] != expected_guides:
            raise RuntimeError("live MCP guide payloads differ from release documents")
        required_uris = set(expected_guides) | {
            "resource://plan-manager/build_info.json"
        }
        if not required_uris.issubset(observed["listed_uris"]):
            raise RuntimeError("installed MCP resources are not discoverable")
        identity = observed["identity"]
        if identity["product_version"] != wheel_version:
            raise RuntimeError(
                "runtime product version differs from wheel metadata: "
                f"{identity['product_version']} != {wheel_version}"
            )
        if observed["build_info_resource"] != identity:
            raise RuntimeError("build_info.json differs from canonical identity")
        if identity["source_revision"] != expected_revision:
            raise RuntimeError(
                "installed source revision mismatch: "
                f"{identity['source_revision']} != {expected_revision}"
            )
        if observed["server_version"] != identity["product_version"]:
            raise RuntimeError("MCP serverInfo.version is not the product version")
        if observed["protocol_version"] != "2025-06-18":
            raise RuntimeError(
                "MCP protocol version was conflated with product version"
            )
        if observed["health"] != {"status": "ok"}:
            raise RuntimeError("health contract changed")
        if observed["tool_count"] != 27:
            raise RuntimeError("installed MCP tool inventory changed")
        tool_contract_bytes = json.dumps(
            observed["tool_contract"],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        tool_contract_hash = hashlib.sha256(tool_contract_bytes).hexdigest()
        if tool_contract_hash != _TOOL_CONTRACT_SHA256:
            raise RuntimeError(
                "installed MCP tool contract changed: "
                f"{tool_contract_hash} != {_TOOL_CONTRACT_SHA256}"
            )

        stepped_actions = observed["stepped_actions"]
        recommended = [item for item in stepped_actions if item["recommended"]]
        if [item["name"] for item in recommended] != ["start_task"]:
            raise RuntimeError("ready task does not recommend start_task")
        if recommended[0]["who"] != "AGENT":
            raise RuntimeError("start_task still requests duplicate approval")
        if not any(item["name"] == "authority_boundary" for item in stepped_actions):
            raise RuntimeError("missing-authority branch is absent")
        if any(
            item["name"] == "user_execute_instruction"
            for item in observed["started_actions"]
        ):
            raise RuntimeError("installed workflow still requests execute token")
        submitted_actions = observed["submitted_actions"]
        for name in ("approve_pr", "merge_pr"):
            action = next(item for item in submitted_actions if item["name"] == name)
            if action["who"] != "AGENT_AFTER_USER_APPROVAL":
                raise RuntimeError(f"{name} lost owner-review boundary")
        approve = next(
            item for item in submitted_actions if item["name"] == "approve_pr"
        )
        if "worker completion" not in approve["label"]:
            raise RuntimeError("worker output is not distinguished from owner review")

        cli = subprocess.run(
            [sys.executable, "-m", "plan_manager", "--version"],
            cwd=temp,
            env=env,
            check=True,
            text=True,
            capture_output=True,
        ).stdout
        expected_line = (
            "plan-manager "
            f"product_version={identity['product_version']} "
            f"source_revision={identity['source_revision']}\n"
        )
        if cli != expected_line:
            raise RuntimeError(f"CLI identity mismatch: {cli!r}")

    with tempfile.TemporaryDirectory(
        prefix="plan-manager-dependency-install-"
    ) as install_name:
        install_root = Path(install_name)
        venv = install_root / "venv"
        subprocess.run(
            ["uv", "venv", "--python", sys.executable, str(venv)],
            check=True,
            text=True,
            capture_output=True,
        )
        venv_python = venv / "bin" / "python"
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(venv_python),
                str(wheel),
            ],
            check=True,
            text=True,
            capture_output=True,
        )
        install_env = dict(os.environ)
        install_env.pop("PYTHONPATH", None)
        install_env["PLAN_MANAGER_DB_DIR"] = str(install_root / "db")
        install_env["TODO_DIR"] = str(install_root / "todo")
        installed = subprocess.run(
            [
                str(venv_python),
                "-c",
                (
                    "import json; "
                    "from plan_manager.identity import build_identity; "
                    "from plan_manager.server.app import starlette_app; "
                    "assert starlette_app; "
                    "print(json.dumps(build_identity(), sort_keys=True))"
                ),
            ],
            cwd=install_root,
            env=install_env,
            check=True,
            text=True,
            capture_output=True,
        )
        installed_json = next(
            line
            for line in reversed(installed.stdout.splitlines())
            if line.startswith("{")
        )
        installed_identity = json.loads(installed_json)
        if installed_identity != identity:
            raise RuntimeError(
                "declared-dependency install identity differs from built artifact"
            )

    sys.stdout.write(
        json.dumps(
            {
                "wheel": wheel.name,
                "sha256": digest,
                "product_version": identity["product_version"],
                "source_revision": identity["source_revision"],
            },
            sort_keys=True,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
