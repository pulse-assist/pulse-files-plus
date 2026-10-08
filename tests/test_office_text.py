from files_plus.office_text import extract_text
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_docx_template_text():
    data = (ROOT / "templates" / "new.docx").read_bytes()
    text = extract_text(data, "new.docx")
    assert isinstance(text, str)


def test_xlsx_and_pptx_templates():
    for name in ("new.xlsx", "new.pptx"):
        data = (ROOT / "templates" / name).read_bytes()
        assert extract_text(data, name) is not None
