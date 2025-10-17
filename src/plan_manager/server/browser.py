from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, Response

from plan_manager.config import TODO_DIR

CSS_STYLE = """
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 16px;
        line-height: 1.6;
        background-color: #1e1e1e;
        color: #d4d4d4;
        padding: 2rem;
        margin: 0;
    }
    .container {
        margin: 0 auto;
        background-color: #252526;
        border: 1px solid #333333;
        border-radius: 8px;
        padding: 2rem;
    }
    h2 {
        font-size: 1.75rem;
        color: #ffffff;
        border-bottom: 1px solid #333333;
        padding-bottom: 0.5rem;
        margin-top: 0;
    }
    ul {
        list-style-type: none;
        padding: 0;
    }
    li {
        margin: 0.5rem 0;
        padding: 0.5rem 0;
    }
    a {
        text-decoration: none;
        color: #3794ff;
    }
    a:hover {
        text-decoration: underline;
    }
"""


async def browse_endpoint(request: Request) -> Response:
    """Serves files and directory listings for the /browse path."""
    relative_path = request.path_params.get("path", "")

    try:
        # Ensure the base directory exists; if not, create it so /browse/ works
        # from a clean repo
        base_dir = Path(TODO_DIR)
        base_dir.mkdir(parents=True, exist_ok=True)
        base_root = base_dir.resolve()

        # Resolve the requested path safely within the base directory
        file_path = (base_dir / relative_path).resolve()
        if not file_path.is_relative_to(base_root):
            raise HTTPException(status_code=403, detail="Forbidden")

        # If a non-root path is requested but doesn't exist, return 404
        if relative_path and not file_path.exists():
            raise HTTPException(status_code=404, detail="Not Found")
    except HTTPException:
        raise
    except (OSError, ValueError, RuntimeError) as e:
        # OSError: file system errors
        # ValueError: invalid path operations
        # RuntimeError: path resolution errors
        raise HTTPException(status_code=500, detail="Server Error") from e

    if file_path.is_dir():
        html = f"""
        <html>
            <head>
                <title>Browse: /{relative_path}</title>
                <style>{CSS_STYLE}</style>
            </head>
            <body>
                <div class="container">
                    <h2>Directory: /{relative_path}</h2>
                    <ul>
        """
        if relative_path:
            parent = Path(relative_path).parent
            parent_link = f"/browse/{parent}" if str(parent) != "." else "/browse/"
            html += f'<li><a href="{parent_link}">.. (Parent Directory)</a></li>'

        items = sorted(file_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))

        for item in items:
            item_name = item.name
            link_path = item.relative_to(base_dir)
            if item.is_dir():
                item_name += "/"
            html += f'<li><a href="/browse/{link_path}">{item_name}</a></li>'
        html += """
                    </ul>
                </div>
            </body>
        </html>
        """
        return HTMLResponse(html)

    if file_path.is_file():
        return FileResponse(file_path)

    raise HTTPException(status_code=404, detail="Not Found")
