from pathlib import Path

import json

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_has_embed_and_services():
    m = json.loads((ROOT / "pulse-plugin.json").read_text(encoding="utf-8"))
    assert m["id"] == "files-plus"
    assert set(m["permissions"]) >= {"embed", "files:open", "services", "notify"}
    assert m["runtime"]["kind"] == "docker"
    assert m["services"][0]["id"] == "docs"
    assert "@sha256:" in m["services"][0]["image"]
    assert m["files"]["handlers"]
    assert len(m["files"]["templates"]) == 3
    for t in m["files"]["templates"]:
        assert (ROOT / t["file"]).is_file()
