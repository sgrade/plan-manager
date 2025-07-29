"""Entry point for running the Plan Manager MCP server.

This module configures and starts the uvicorn ASGI server hosting the MCP server
for AI-assisted task management. The server provides SSE-based transport for
communication with AI assistants like Cursor.

Usage:
    python -m plan_manager
    uv run python -m plan_manager
"""

import uvicorn
import logging
import os

from .mcp_server import app, LOG_FILE_PATH

def main():
    """Main entry point for the plan-manager console script."""
    logging.info(f"Starting MCP Plan Manager Server on 0.0.0.0:8000. App logs: {LOG_FILE_PATH}")

    # The server is started in a simple, stable mode.
    # To apply changes, you must manually stop (Ctrl+C) and restart the server.
    uvicorn.run(
        "plan_manager.mcp_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    main()
