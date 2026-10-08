"""Extract plain text from office files without OnlyOffice (stdlib)."""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
A_NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
SS_NS = {"ss": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def extract_text(data: bytes, name: str, max_chars: int = 200_000) -> str:
    ext = Path(name).suffix.lower().lstrip(".")
    if ext == "csv":
        text = data.decode("utf-8", errors="replace")
    elif ext in ("docx", "odt"):
        text = _docx(data) if ext == "docx" else _odf_text(data)
    elif ext in ("xlsx", "ods"):
        text = _xlsx(data) if ext == "xlsx" else _odf_text(data)
    elif ext in ("pptx", "odp"):
        text = _pptx(data) if ext == "pptx" else _odf_text(data)
    else:
        text = f"[бинарный формат .{ext}: откройте в редакторе или конвертируйте]"
    if len(text) > max_chars:
        return text[:max_chars] + "\n…(обрезано)"
    return text


def _docx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    parts = [node.text or "" for node in root.findall(".//w:t", W_NS)]
    return "\n".join(p for p in "".join(parts).split("\n") if p is not None)


def _pptx(data: bytes) -> str:
    lines: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        slides = sorted(n for n in zf.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml"))
        for i, name in enumerate(slides, 1):
            root = ET.fromstring(zf.read(name))
            texts = [n.text or "" for n in root.findall(".//a:t", A_NS)]
            body = " ".join(t for t in texts if t).strip()
            lines.append(f"## Слайд {i}\n{body}")
    return "\n\n".join(lines)


def _xlsx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root:
                shared.append("".join(t.text or "" for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")))
        sheets = sorted(n for n in zf.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))
        chunks: list[str] = []
        for idx, sheet in enumerate(sheets, 1):
            root = ET.fromstring(zf.read(sheet))
            rows: list[str] = []
            for row in root.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"):
                cells = []
                for c in row:
                    t = c.attrib.get("t")
                    v = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                    val = v.text if v is not None else ""
                    if t == "s" and val.isdigit() and int(val) < len(shared):
                        val = shared[int(val)]
                    cells.append(val or "")
                if any(cells):
                    rows.append("\t".join(cells))
            chunks.append(f"## Лист {idx}\n" + "\n".join(rows))
        return "\n\n".join(chunks)


def _odf_text(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        if "content.xml" not in zf.namelist():
            return ""
        root = ET.fromstring(zf.read("content.xml"))
    return " ".join(t.strip() for t in root.itertext() if t.strip())
