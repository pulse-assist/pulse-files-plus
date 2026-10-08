from files_plus.http_headers import content_disposition


def test_content_disposition_cyrillic_is_latin1_safe():
    header = content_disposition("2026-10-07 презентация платформы Пульс.pptx")
    header.encode("latin-1")
    assert "filename*=UTF-8''" in header
    assert "pptx" in header
    assert "презентация" not in header.split("filename*=")[0]


def test_content_disposition_ascii_passthrough():
    header = content_disposition("report.pptx")
    header.encode("latin-1")
    assert 'filename="report.pptx"' in header
