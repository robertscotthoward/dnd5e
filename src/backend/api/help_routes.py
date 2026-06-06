"""Help wiki routes — serves Markdown files from docs/help/."""

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse

router = APIRouter(prefix="/help", tags=["help"])

_HELP_ROOT = Path(__file__).parent.parent.parent.parent / "docs" / "help"


def _safe_resolve(relative: str) -> Path:
    """Resolve path and ensure it stays within _HELP_ROOT."""
    if not relative.endswith(".md"):
        relative = relative + ".md"
    resolved = (_HELP_ROOT / relative).resolve()
    if not str(resolved).startswith(str(_HELP_ROOT.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    return resolved


@router.get("/search")
async def search_help(q: str = Query(..., min_length=1)):
    """Search all .md files under docs/help/ for the query string."""
    pattern = re.compile(re.escape(q), re.IGNORECASE)
    results = []
    for md_file in sorted(_HELP_ROOT.glob("**/*.md")):
        content = md_file.read_text(encoding="utf-8")
        if pattern.search(content):
            rel = md_file.relative_to(_HELP_ROOT).as_posix()
            # Extract first heading as title
            title_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
            title = title_match.group(1) if title_match else rel
            results.append({"path": rel, "title": title})
    return JSONResponse(content={"results": results})


@router.get("/{path:path}", response_class=PlainTextResponse)
async def get_help_page(path: str) -> str:
    """Return the raw Markdown content of a help page."""
    if not path or path == "/":
        path = "home.md"
    file_path = _safe_resolve(path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Help page not found: {path}")
    return file_path.read_text(encoding="utf-8")
