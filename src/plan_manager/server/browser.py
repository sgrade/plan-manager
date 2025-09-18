from pathlib import Path

from starlette.responses import HTMLResponse, FileResponse
from starlette.exceptions import HTTPException

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


async def browse_endpoint(request):
    """Serves files and directory listings for the /browse path."""
    relative_path = request.path_params.get("path", "")

    try:
        base_dir = Path(TODO_DIR).resolve(strict=True)
        file_path = base_dir.joinpath(relative_path).resolve(strict=True)
        if not file_path.is_relative_to(base_dir):
            raise HTTPException(status_code=403, detail="Forbidden")
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Not Found")
    except Exception:
        raise HTTPException(status_code=500, detail="Server Error")

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
            parent_link = f"/browse/{parent}" if str(
                parent) != "." else "/browse/"
            html += f'<li><a href="{parent_link}">.. (Parent Directory)</a></li>'

        items = sorted(list(file_path.iterdir()),
                       key=lambda p: (p.is_file(), p.name.lower()))

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

    elif file_path.is_file():
        return FileResponse(file_path)
