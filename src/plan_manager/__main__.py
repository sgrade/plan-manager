"""Entry point for running the Plan Manager MCP server.

Usage:
    # Dev (auto-reload)
    uv run plan-manager --reload

    # Prod (no reload)
    uv run plan-manager
"""
import argparse
import logging
import os
import uvicorn

from .mcp_server import app, LOG_FILE_PATH


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def main():
    parser = argparse.ArgumentParser(description="Run the Plan Manager MCP server.")
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "info"))
    parser.add_argument("--timeout-graceful-shutdown", type=int, default=int(os.getenv("TIMEOUT_GRACEFUL_SHUTDOWN", "2")))
    parser.add_argument("--timeout-keep-alive", type=int, default=int(os.getenv("TIMEOUT_KEEP_ALIVE", "2")))
    parser.add_argument("--reload", action=argparse.BooleanOptionalAction, default=_env_bool("PLAN_MANAGER_RELOAD", False))
    parser.add_argument("--reload-dir", action="append", default=os.getenv("RELOAD_DIRS", "src").split(","))
    parser.add_argument("--reload-include", action="append", default=os.getenv("RELOAD_INCLUDE", "*.py").split(","))
    parser.add_argument("--reload-exclude", action="append", default=os.getenv("RELOAD_EXCLUDE", "logs/*").split(","))
    args = parser.parse_args()

    logging.info(
        f"Starting MCP Plan Manager Server on {args.host}:{args.port} (reload={args.reload}). App logs: {LOG_FILE_PATH}"
    )

    uvicorn.run(
        "plan_manager.mcp_server:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=bool(args.reload),
        reload_dirs=[d for d in args.reload_dir if d],
        reload_includes=[p for p in args.reload_include if p],
        reload_excludes=[p for p in args.reload_exclude if p],
        timeout_graceful_shutdown=args.timeout_graceful_shutdown,
        timeout_keep_alive=args.timeout_keep_alive,
    )


if __name__ == "__main__":
    main()
