"""MCP Server (SSE Transport) for the plan-manager.

Exposes story and plan tools over SSE for IDE agents via FastMCP.
"""

import os
import sys
import logging

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount

from plan_manager.stories import register_story_tools
from plan_manager.archive import register_archive_tools
from plan_manager.plan import register_plan_tools
from plan_manager.plan import register_plan_tools


# --- Logging Setup ---
LOG_DIR = os.path.join(os.getcwd(), 'logs')
LOG_FILE_PATH = os.path.join(LOG_DIR, 'mcp_server_app.log')
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s')

for handler in logger.handlers[:]:
    logger.removeHandler(handler)

stream_handler = logging.StreamHandler(sys.stderr)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

ENABLE_FILE_LOG = os.getenv("PLAN_MANAGER_ENABLE_FILE_LOG", "true").lower() in ("1","true","yes","on")
if ENABLE_FILE_LOG:
    file_handler = logging.FileHandler(LOG_FILE_PATH)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

logging.info(f"MCP server application logging configured. App logs will also be in: {LOG_FILE_PATH}")

# --- MCP Server Initialization ---
mcp = FastMCP(
    name="plan-manager",
    instructions="Manages stories defined in the project's plan.",
    sse_path="/sse",
    message_path="/messages/"
)

register_story_tools(mcp)
register_archive_tools(mcp)
register_plan_tools(mcp)

# --- ASGI Application Setup ---
# SSE transport only
app = Starlette(
    debug=True,
    routes=[
        Mount('/', app=mcp.sse_app()),
    ]
)
