"""HTTP header helpers (latin-1-safe values for Starlette/ASGI)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote


def content_disposition(filename: str) -> str:
    """Build Content-Disposition with ASCII fallback + RFC 5987 filename*."""
    name = Path(filename).name or "document"
    ascii_name = (
        name.encode("ascii", "replace")
        .decode("ascii")
        .replace('"', "")
        .replace("\\", "")
        .replace("\r", "")
        .replace("\n", "")
    )
    if not ascii_name.strip("?._- ") or set(ascii_name) <= {"?"}:
        ascii_name = f"document{Path(name).suffix}"
    return (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(name, safe='')}"
    )
