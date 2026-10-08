"""Smoke: editor module must import urllib.parse.quote (used in /editor URLs)."""

from pathlib import Path


def test_app_imports_quote():
    src = Path(__file__).resolve().parents[1] / "backend" / "files_plus" / "app.py"
    text = src.read_text(encoding="utf-8")
    assert "from urllib.parse import quote" in text
    assert "quote(download_tok" in text
    assert "quote(callback_tok" in text
