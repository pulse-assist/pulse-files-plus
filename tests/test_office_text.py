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


SS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def _xlsx(sheets: dict[str, str], shared: list[str] | None = None) -> bytes:
    """xlsx вручную: листы {имя: <sheetData>…}, файлы sheet2.xml, sheet10.xml — чтобы проверить порядок по книге."""
    import io
    import zipfile

    buf = io.BytesIO()
    numbers = [2, 10, 3][: len(sheets)]
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("xl/workbook.xml", f'<workbook {SS} {R}><sheets>' + "".join(
            f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>' for i, name in enumerate(sheets, 1)) + "</sheets></workbook>")
        zf.writestr("xl/_rels/workbook.xml.rels",
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(
                        f'<Relationship Id="rId{i}" Target="worksheets/sheet{n}.xml"/>'
                        for i, n in enumerate(numbers, 1)) + "</Relationships>")
        for n, data in zip(numbers, sheets.values()):
            zf.writestr(f"xl/worksheets/sheet{n}.xml", f"<worksheet {SS}><sheetData>{data}</sheetData></worksheet>")
        if shared is not None:
            zf.writestr("xl/sharedStrings.xml", f"<sst {SS}>" + "".join(shared) + "</sst>")
    return buf.getvalue()


def test_xlsx_inline_strings_sheet_names_and_order():
    """inlineStr — строка прямо в ячейке (без sharedStrings): раньше выходили одни числа и «Лист 1» (TASK-57)."""
    data = _xlsx({
        "Продажи": '<row r="1"><c r="A1" t="inlineStr"><is><t>Регион</t></is></c><c r="B1" t="inlineStr"><is><t>Сумма</t></is></c></row>'
                   '<row r="2"><c r="A2" t="inlineStr"><is><r><t>Моск</t></r><r><t>ва</t></r></is></c><c r="B2"><v>1500.5</v></c></row>',
        "Итоги": '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1"><v>42</v></c></row>',
    }, shared=["<si><t>Всего</t><rPh><t>фонетика</t></rPh></si>"])
    text = extract_text(data, "отчёт.xlsx")
    assert text == "## Продажи\nРегион\tСумма\nМосква\t1500.5\n\n## Итоги\nВсего\t42"


def test_xlsx_without_workbook_keeps_numeric_sheet_order():
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for n in (10, 2):
            zf.writestr(f"xl/worksheets/sheet{n}.xml", f'<worksheet {SS}><sheetData><row><c t="inlineStr"><is><t>лист {n}</t></is></c></row></sheetData></worksheet>')
    assert extract_text(buf.getvalue(), "x.xlsx") == "## Лист 1\nлист 2\n\n## Лист 2\nлист 10"
