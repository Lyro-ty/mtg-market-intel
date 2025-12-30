"""
Documentation access tools for MCP server.

Provides tools to read project documentation and design docs.
"""
from typing import Any
from pathlib import Path

from mcp_server.config import config


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(config.project_root)


async def get_design_docs() -> dict[str, Any]:
    """
    List all design documents in docs/plans/.

    Returns:
        List of design docs with names and first lines
    """
    docs_dir = get_project_root() / "docs" / "plans"

    if not docs_dir.exists():
        return {"error": "docs/plans/ directory not found"}

    docs = []
    for file_path in sorted(docs_dir.glob("*.md")):
        # Read first few lines for summary
        try:
            with open(file_path, "r") as f:
                lines = f.readlines()[:5]
                title = lines[0].strip().lstrip("#").strip() if lines else file_path.stem

            docs.append({
                "filename": file_path.name,
                "title": title,
                "path": str(file_path.relative_to(get_project_root())),
            })
        except Exception as e:
            docs.append({
                "filename": file_path.name,
                "error": str(e),
            })

    return {
        "count": len(docs),
        "documents": docs,
    }


async def read_design_doc(filename: str) -> dict[str, Any]:
    """
    Read a specific design document.

    Args:
        filename: Name of the document (with or without .md extension)

    Returns:
        Document content
    """
    if not filename.endswith(".md"):
        filename += ".md"

    file_path = get_project_root() / "docs" / "plans" / filename

    if not file_path.exists():
        # Try to find similar files
        docs_dir = get_project_root() / "docs" / "plans"
        similar = [f.name for f in docs_dir.glob("*.md") if filename.replace(".md", "") in f.name]
        return {
            "error": f"Document '{filename}' not found",
            "similar": similar,
        }

    try:
        content = file_path.read_text()
        return {
            "filename": filename,
            "path": str(file_path.relative_to(get_project_root())),
            "content": content,
            "lines": len(content.split("\n")),
        }
    except Exception as e:
        return {"error": str(e)}


async def get_claude_md() -> dict[str, Any]:
    """
    Read the CLAUDE.md project instructions file.

    Returns:
        CLAUDE.md content
    """
    file_path = get_project_root() / "CLAUDE.md"

    if not file_path.exists():
        return {"error": "CLAUDE.md not found"}

    try:
        content = file_path.read_text()
        return {
            "filename": "CLAUDE.md",
            "content": content,
            "lines": len(content.split("\n")),
        }
    except Exception as e:
        return {"error": str(e)}
