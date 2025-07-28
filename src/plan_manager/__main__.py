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
    # Get the directory of the plan_manager package itself
    package_dir = os.path.dirname(os.path.abspath(__file__))

    logging.info(f"Starting MCP Plan Manager Server from __main__.py on 0.0.0.0:8000. App logs: {LOG_FILE_PATH}")

    # Note: reload=False for production stability
    # reload_dirs can be specified if you want to watch specific directories
    uvicorn.run(
        "plan_manager.mcp_server:app",  # Pass as an import string for reload to work
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disabled for production stability
        reload_dirs=[package_dir],  # Watch the plan_manager directory for changes
        log_level="info"  # Set uvicorn's own log level
    )


if __name__ == "__main__":
    main()
