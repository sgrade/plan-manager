# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""Entry point for running the Plan Manager MCP server."""

import argparse
import json
import logging
import sqlite3
import sys
from importlib import import_module
from pathlib import Path

import uvicorn

# --- Configuration Bootstrap ---
# This is the first and only place where these modules should be imported to
# ensure that configuration and logging are set up exactly once, as soon as
# the application starts. The order is critical.
from plan_manager import config
from plan_manager.storage.db import DB_FILENAME, bootstrap, startup_storage
from plan_manager.storage.exporter import export_tree
from plan_manager.storage.importer import (
    LegacyImportError,
    import_legacy_tree,
    replace_plan_from_tree,
)
from plan_manager.storage.offline_guard import (
    LiveServerDetectedError,
    hold_server_lock,
    require_offline,
)

logger = logging.getLogger(__name__)


def _serve() -> int:
    # Logging bootstrap is only required for the server lifecycle.
    import_module("plan_manager.logging")
    with hold_server_lock(config.PLAN_MANAGER_DB_DIR):
        try:
            startup_storage(config.TODO_DIR, config.PLAN_MANAGER_DB_DIR)
        except Exception as exc:
            logger.exception("Storage startup failed.")
            raise SystemExit(f"Storage startup failed: {exc}") from exc

        log_destination = (
            config.LOG_FILE_PATH if config.ENABLE_FILE_LOG else "stdout only"
        )
        logger.info(
            "Starting MCP Plan Manager Server on %s:%s (reload=%s). App logs to: %s",
            config.HOST,
            config.PORT,
            config.RELOAD,
            log_destination,
        )

        if config.RELOAD:
            logger.info(
                "Reloading enabled. Reload dirs: %s, includes: %s, excludes: %s",
                config.RELOAD_DIRS,
                config.RELOAD_INCLUDES,
                config.RELOAD_EXCLUDES,
            )
        else:
            logger.info("Reloading disabled. App will not restart on code changes.")

        uvicorn.run(
            "plan_manager.server.app:starlette_app",
            factory=True,
            # IMPORTANT: This tells uvicorn to use our configuration above.
            log_config=None,
            host=config.HOST,
            port=config.PORT,
            reload=config.RELOAD,
            reload_dirs=[d for d in config.RELOAD_DIRS if d],
            reload_includes=[p for p in config.RELOAD_INCLUDES if p],
            reload_excludes=[p for p in config.RELOAD_EXCLUDES if p],
            timeout_graceful_shutdown=config.TIMEOUT_GRACEFUL_SHUTDOWN,
            timeout_keep_alive=config.TIMEOUT_KEEP_ALIVE,
        )
    return 0


def _run_export(args: argparse.Namespace) -> int:
    require_offline(config.PLAN_MANAGER_DB_DIR)
    report = export_tree(
        db_dir=config.PLAN_MANAGER_DB_DIR,
        out_dir=args.out,
        plan_id=args.plan,
    )
    sys.stdout.write(
        json.dumps(
            {
                "ok": True,
                "published": True,
                "out_dir": report.out_dir,
                "plans": report.plans,
                "stories": report.stories,
                "tasks": report.tasks,
                "events": report.events,
                "event_seq_range": {"min": report.seq_min, "max": report.seq_max},
                "content_hash": report.content_hash,
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 0


def _run_import(args: argparse.Namespace) -> int:
    require_offline(config.PLAN_MANAGER_DB_DIR)
    source_dir = Path(args.from_dir)
    db_path = Path(config.PLAN_MANAGER_DB_DIR) / DB_FILENAME
    if args.replace_plan:
        bootstrap(config.PLAN_MANAGER_DB_DIR)
        report = replace_plan_from_tree(
            todo_dir=source_dir,
            db_path=db_path,
            replace_plan_id=args.replace_plan,
            dry_run=args.dry_run,
        )
    else:
        if not args.dry_run and _existing_plan_count(db_path) > 0:
            raise RuntimeError(
                "Refusing to overwrite existing plans without --replace-plan."
            )
        report = import_legacy_tree(
            todo_dir=source_dir,
            db_dir=config.PLAN_MANAGER_DB_DIR,
            dry_run=args.dry_run,
        )
    sys.stdout.write(
        json.dumps(
            {
                "ok": report.ok,
                "dry_run": report.dry_run,
                "published": report.published,
                "plans": report.plans,
                "stories": report.stories,
                "tasks": report.tasks,
                "events": report.events,
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 0


def _existing_plan_count(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    try:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute("SELECT COUNT(*) FROM plans").fetchone()
            if row is None:
                return 0
            return int(row[0])
        finally:
            conn.close()
    except sqlite3.Error:
        return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pm")
    subparsers = parser.add_subparsers(dest="command")

    export_parser = subparsers.add_parser(
        "export",
        help="Export SQLite snapshot into YAML tree.",
    )
    export_parser.add_argument("--plan", help="Export one plan ID only.", default=None)
    export_parser.add_argument(
        "--out",
        help="Export output directory.",
        default=config.TODO_DIR,
    )

    import_parser = subparsers.add_parser(
        "import",
        help="Import YAML tree into SQLite.",
    )
    import_parser.add_argument("--dry-run", action="store_true", help="Validate only.")
    import_parser.add_argument(
        "--replace-plan",
        help="Replace exactly one plan atomically.",
        default=None,
    )
    import_parser.add_argument(
        "--from",
        dest="from_dir",
        help="Import source directory.",
        default=config.TODO_DIR,
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            code = _run_export(args)
        elif args.command == "import":
            code = _run_import(args)
        else:
            code = _serve()
    except LegacyImportError as exc:
        sys.stderr.write(f"{exc}\n")
        raise SystemExit(1) from exc
    except (LiveServerDetectedError, RuntimeError) as exc:
        sys.stderr.write(f"{exc}\n")
        raise SystemExit(1) from exc
    raise SystemExit(code)


if __name__ == "__main__":
    main()
