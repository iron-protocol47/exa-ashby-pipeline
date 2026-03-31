"""Single-page admin UI for webset → Ashby project mappings."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["admin-ui"])

_HTML_PATH = Path(__file__).resolve().parent.parent / "static" / "admin.html"


@router.get("/admin", response_class=HTMLResponse)
def admin_page() -> HTMLResponse:
    html = _HTML_PATH.read_text(encoding="utf-8")
    return HTMLResponse(content=html)
