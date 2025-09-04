from plan_manager.schemas.inputs import PreviewChangelogIn, GenerateChangelogIn, PublishChangelogIn
from plan_manager.schemas.outputs import ChangelogPreviewOut, OperationResult
from plan_manager.services.changelog_service import render_changelog, publish_changelog


def register_changelog_tools(mcp_instance) -> None:
    """Register changelog tools with the MCP instance."""
    mcp_instance.tool()(preview_changelog)
    mcp_instance.tool()(generate_changelog)
    mcp_instance.tool()(publish_changelog_tool)


def preview_changelog(payload: PreviewChangelogIn) -> ChangelogPreviewOut:
    """Preview a changelog snippet generated from recent activity."""
    md = render_changelog(payload.version, payload.date)
    return ChangelogPreviewOut(markdown=md)


def generate_changelog(payload: GenerateChangelogIn) -> ChangelogPreviewOut:
    """Generate a changelog snippet (same as preview, returned as markdown)."""
    md = render_changelog(payload.version, payload.date)
    return ChangelogPreviewOut(markdown=md)


def publish_changelog_tool(payload: PublishChangelogIn) -> OperationResult:
    """Append a generated changelog snippet to a file (default CHANGELOG.md)."""
    md = render_changelog(payload.version, payload.date)
    publish_changelog(md, payload.target_path or 'CHANGELOG.md')
    return OperationResult(success=True, message=f"Changelog appended to {payload.target_path or 'CHANGELOG.md'}")
