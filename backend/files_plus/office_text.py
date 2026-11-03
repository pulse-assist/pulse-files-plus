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


_SS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def _string_item(node) -> str:
    """Текст строки xlsx (<si> или <is>): простой <t> или куски <r><t>; подсказки чтения (<rPh>) — не текст."""
    parts = []
    for child in node:
        if child.tag == f"{_SS}t":
            parts.append(child.text or "")
        elif child.tag == f"{_SS}r":
            parts.extend(t.text or "" for t in child.iter(f"{_SS}t"))
    return "".join(parts)


def _xlsx_sheets(zf: zipfile.ZipFile) -> list[tuple[str, str]]:
    """Листы в порядке книги: [(имя, путь в архиве)]. Без workbook.xml — файлы sheetN.xml по номеру."""
    names = zf.namelist()
    found = [n for n in names if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]
    by_number = sorted(found, key=lambda n: int("".join(ch for ch in Path(n).stem if ch.isdigit()) or 0))
    if "xl/workbook.xml" not in names:
        return [(f"Лист {i}", n) for i, n in enumerate(by_number, 1)]
    targets: dict[str, str] = {}
    if "xl/_rels/workbook.xml.rels" in names:
        for rel in ET.fromstring(zf.read("xl/_rels/workbook.xml.rels")).iter(f"{_PKG_REL}Relationship"):
            target = rel.attrib.get("Target", "").lstrip("/")
            targets[rel.attrib.get("Id", "")] = target if target.startswith("xl/") else f"xl/{target}"
    sheets: list[tuple[str, str]] = []
    for i, sheet in enumerate(ET.fromstring(zf.read("xl/workbook.xml")).iter(f"{_SS}sheet"), 1):
        path = targets.get(sheet.attrib.get(f"{_REL}id", ""), "")
        if path not in names and i <= len(by_number):
            path = by_number[i - 1]
        if path in names:
            sheets.append((sheet.attrib.get("name") or f"Лист {i}", path))
    return sheets or [(f"Лист {i}", n) for i, n in enumerate(by_number, 1)]


def _xlsx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            shared = [_string_item(si) for si in ET.fromstring(zf.read("xl/sharedStrings.xml")).findall(f"{_SS}si")]
        chunks: list[str] = []
        for name, sheet in _xlsx_sheets(zf):
            root = ET.fromstring(zf.read(sheet))
            rows: list[str] = []
            for row in root.iter(f"{_SS}row"):
                cells = []
                for c in row.findall(f"{_SS}c"):
                    t = c.attrib.get("t")
                    v = c.find(f"{_SS}v")
                    val = v.text if v is not None and v.text is not None else ""
                    if t == "s" and val.isdigit() and int(val) < len(shared):
                        val = shared[int(val)]
                    elif t == "inlineStr":
                        # строка прямо в ячейке (<is>) — так пишут openpyxl в потоковом режиме, выгрузки 1С и т.п.
                        inline = c.find(f"{_SS}is")
                        val = _string_item(inline) if inline is not None else val
                    cells.append(val or "")
                if any(cells):
                    rows.append("\t".join(cells))
            chunks.append(f"## {name}\n" + "\n".join(rows))
        return "\n\n".join(chunks)


def _odf_text(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        if "content.xml" not in zf.namelist():
            return ""
        root = ET.fromstring(zf.read("content.xml"))
    return " ".join(t.strip() for t in root.itertext() if t.strip())
