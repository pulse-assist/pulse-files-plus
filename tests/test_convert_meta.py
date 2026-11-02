"""convert/info: plugin.file(arg) даёт meta без version — берём полные метаданные у ядра."""

from files_plus import app as fp


class _Ticket:
    def __init__(self, ticket, meta):
        self.ticket = ticket
        self._meta = meta

    def meta(self):
        return self._meta


def test_full_meta_fetches_version(monkeypatch):
    core = {"path": "a/b.pptx", "name": "b.pptx", "version": "v7", "size": 10, "access": "read"}
    monkeypatch.setattr(fp.plugin, "file_ticket", lambda t: _Ticket(t, core))
    partial = _Ticket("t1", {"path": "a/b.pptx", "name": "b.pptx"})
    assert fp._full_meta(partial)["version"] == "v7"


def test_full_meta_keeps_complete(monkeypatch):
    def boom(_):
        raise AssertionError("лишний запрос к ядру")

    monkeypatch.setattr(fp.plugin, "file_ticket", boom)
    full = _Ticket("t1", {"path": "p", "name": "n", "version": None})
    assert fp._full_meta(full)["path"] == "p"


def test_convert_key_depends_on_format():
    assert fp._doc_key("p", "v:pdf") != fp._doc_key("p", "v:docx")
