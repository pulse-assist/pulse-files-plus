"""PulseFiles+ runtime: OnlyOffice editor page, download/callback, agent commands."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from pathlib import Path
from typing import Any
import httpx
import jwt
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from pulse_plugin import CommandError, Plugin

from files_plus.http_headers import content_disposition
from files_plus.office_text import extract_text

log = logging.getLogger("files-plus")
plugin = Plugin("PulseFiles+")
app = plugin.app

SIGN_TTL = 12 * 3600
CONVERT_TIMEOUT = 120


def _jwt_secret() -> str:
    secret = plugin.secret("jwt") or os.environ.get("JWT_SECRET") or ""
    if not secret:
        raise HTTPException(503, "JWT-секрет OnlyOffice ещё не создан")
    return secret


def _sign(payload: dict[str, Any], ttl: int = SIGN_TTL) -> str:
    body = {**payload, "exp": int(time.time()) + ttl}
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    digest = hmac.new(_jwt_secret().encode(), raw, hashlib.sha256).hexdigest()
    return jwt.encode({**body, "sig": digest}, _jwt_secret(), algorithm="HS256")


def _unsign(token: str) -> dict[str, Any]:
    try:
        data = jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(403, f"Подпись недействительна: {exc}") from None
    return data


def _docs_ready() -> bool:
    try:
        url = plugin.service_url("docs").rstrip("/") + "/healthcheck"
        with httpx.Client(timeout=3.0) as client:
            return client.get(url).status_code == 200
    except Exception:  # noqa: BLE001
        return False


def _file_type(name: str) -> str:
    return Path(name).suffix.lower().lstrip(".") or "docx"


def _doc_key(path: str, version: str) -> str:
    return hashlib.sha256(f"{path}:{version}".encode()).hexdigest()[:20]


@app.get("/health")
def health() -> dict:
    docs_ok = _docs_ready()
    return {
        "ok": True,
        "plugin": plugin.id,
        "version": plugin.version,
        "docs": "running" if docs_ok else "starting",
    }


@app.get("/editor")
async def editor(request: Request, ticket: str, mode: str = "edit", theme: str = "light") -> HTMLResponse:
    if not ticket:
        raise HTTPException(400, "Нужен ticket")
    if not _docs_ready():
        return HTMLResponse(_starting_html(), status_code=200)

    meta = plugin.file_ticket(ticket).meta()
    name = meta["name"]
    path = meta["path"]
    version = meta["version"]
    access = meta.get("access") or "read"
    edit = mode == "edit" and access == "write"
    file_type = _file_type(name)
    port = os.environ.get("PULSE_PLUGIN_PORT", "8080")
    download_tok = _sign({"ticket": ticket, "kind": "download"})
    callback_tok = _sign({"ticket": ticket, "kind": "callback", "version": version})
    app_path = plugin.app_path.rstrip("/")
    document_url = f"http://app:{port}/download/{quote(download_tok, safe='')}"
    callback_url = f"http://app:{port}/callback/{quote(callback_tok, safe='')}"
    api_js = f"{app_path}/s/docs/web-apps/apps/api/documents/api.js"

    config = {
        "documentType": _doc_type(file_type),
        "document": {
            "fileType": file_type,
            "key": _doc_key(path, version),
            "title": name,
            "url": document_url,
            "permissions": {
                "edit": edit,
                "download": True,
                "print": True,
            },
        },
        "editorConfig": {
            "mode": "edit" if edit else "view",
            "lang": "ru",
            "region": "ru-RU",
            "callbackUrl": callback_url,
            "user": {"id": "owner", "name": "Владелец"},
            "customization": {
                "autosave": bool(plugin.setting("autosave", True)),
                "forcesave": True,
                "compactHeader": True,
                "toolbarNoTabs": False,
                "uiTheme": "theme-dark" if theme == "dark" else "theme-light",
                "goback": False,
                "feedback": False,
                "help": False,
            },
        },
        "width": "100%",
        "height": "100%",
        "type": "desktop",
    }
    token = jwt.encode(config, _jwt_secret(), algorithm="HS256")
    config["token"] = token
    html = _editor_html(api_js, config, theme)
    return HTMLResponse(html)


def _doc_type(ext: str) -> str:
    if ext in ("xlsx", "xls", "ods", "csv"):
        return "cell"
    if ext in ("pptx", "ppt", "odp"):
        return "slide"
    return "word"


@app.get("/download/{token}")
async def download(token: str) -> StreamingResponse:
    data = _unsign(token)
    if data.get("kind") != "download":
        raise HTTPException(403, "Неверная подпись")
    ticket = data["ticket"]
    ft = plugin.file_ticket(ticket)
    meta = ft.meta()
    content = ft.read()

    def chunks():
        yield content

    return StreamingResponse(
        chunks(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": content_disposition(meta["name"])},
    )


@app.post("/callback/{token}")
async def callback(token: str, request: Request) -> JSONResponse:
    data = _unsign(token)
    if data.get("kind") != "callback":
        raise HTTPException(403, "Неверная подпись")
    # OnlyOffice may send JWT in AuthorizationJwt
    body = await request.json()
    status = int(body.get("status") or 0)
    ticket = data["ticket"]
    version = data.get("version")
    if status in (2, 6):
        url = body.get("url")
        if not url:
            return JSONResponse({"error": 1})
        try:
            with httpx.Client(timeout=120.0) as client:
                raw = client.get(url).content
            result = plugin.file_ticket(ticket).write(
                raw, if_match=version, on_conflict="copy",
            )
            if result.get("saved_as"):
                plugin.signal(
                    "Документ сохранён копией",
                    f"Файл изменился, пока вы его правили. Ваша версия: {result['saved_as']}",
                    priority=70,
                    tags=["pulse-files-plus"],
                )
        except Exception as exc:  # noqa: BLE001
            log.exception("callback save failed")
            plugin.signal(
                "Ошибка сохранения документа",
                str(exc)[:500],
                priority=85,
                tags=["pulse-files-plus"],
            )
            return JSONResponse({"error": 1})
    elif status in (3, 7):
        plugin.signal(
            "Ошибка OnlyOffice",
            f"status={status} body={json.dumps(body, ensure_ascii=False)[:400]}",
            priority=85,
            tags=["pulse-files-plus"],
        )
    return JSONResponse({"error": 0})


@plugin.command("text", "Текст офисного документа")
def cmd_text(args: dict) -> dict:
    ft = plugin.file(args.get("path"))
    meta = ft.meta()
    max_chars = int(args.get("max_chars") or 200_000)
    text = extract_text(ft.read(), meta["name"], max_chars)
    return {"path": meta["path"], "name": meta["name"], "text": text}


@plugin.command("info", "Метаданные документа")
def cmd_info(args: dict) -> dict:
    ft = plugin.file(args.get("path"))
    meta = ft.meta()
    return {
        "path": meta["path"],
        "name": meta["name"],
        "size": meta.get("size"),
        "type": _file_type(meta["name"]),
        "version": meta.get("version"),
        "access": meta.get("access"),
    }


@plugin.command("status", "Состояние редактора")
def cmd_status(args: dict) -> dict:
    return {
        "plugin": plugin.version,
        "docs": "running" if _docs_ready() else "starting",
        "docs_url": os.environ.get("PULSE_SERVICE_DOCS_URL"),
        "app_path": plugin.app_path,
    }


@plugin.command("fonts", "Подхватить шрифты")
def cmd_fonts(args: dict) -> dict:
    fonts = Path(plugin.files_dir) / "Шрифты"
    return {
        "ok": True,
        "message": (
            f"Положите .ttf/.otf в {plugin.folder}/Шрифты/ и перезапустите плагин "
            f"(папка сейчас {'есть' if fonts.is_dir() else 'будет создана'})."
        ),
        "path": str(fonts),
    }


@plugin.command("convert", "Конвертация через OnlyOffice")
def cmd_convert(args: dict) -> dict:
    to = str(args.get("to") or "").lower().lstrip(".")
    if not to:
        raise CommandError("Нужен --to (pdf, docx, …)")
    if not _docs_ready():
        raise CommandError("OnlyOffice ещё запускается — повторите через минуту (pulse files-plus status)")
    ft = plugin.file(args.get("path"))
    meta = ft.meta()
    # Use ConvertService asynchronously — simplified sync poll
    docs = plugin.service_url("docs").rstrip("/")
    port = os.environ.get("PULSE_PLUGIN_PORT", "8080")
    download_tok = _sign({"ticket": meta.get("ticket") or args["path"]["ticket"], "kind": "download"})
    # if path arg was dict with ticket
    if isinstance(args.get("path"), dict):
        download_tok = _sign({"ticket": args["path"]["ticket"], "kind": "download"})
    src_url = f"http://app:{port}/download/{quote(download_tok, safe='')}"
    key = _doc_key(meta["path"], meta["version"]) + f"-{to}"
    payload = {
        "async": False,
        "filetype": _file_type(meta["name"]),
        "key": key[:20],
        "outputtype": to,
        "url": src_url,
    }
    token = jwt.encode(payload, _jwt_secret(), algorithm="HS256")
    try:
        with httpx.Client(timeout=CONVERT_TIMEOUT) as client:
            resp = client.post(
                f"{docs}/ConvertService.ashx",
                json={**payload, "token": token},
                headers={"AuthorizationJwt": f"Bearer {token}"},
            )
            result = resp.json()
    except Exception as exc:  # noqa: BLE001
        raise CommandError(f"ConvertService: {exc}") from None
    if not result.get("endConvert") and result.get("error"):
        raise CommandError(f"Конвертация не удалась: {result}")
    file_url = result.get("fileUrl")
    if not file_url:
        raise CommandError(f"Нет fileUrl в ответе: {result}")
    with httpx.Client(timeout=CONVERT_TIMEOUT) as client:
        out_bytes = client.get(file_url).content

    out_arg = args.get("out")
    if isinstance(out_arg, dict) and out_arg.get("ticket"):
        written = plugin.file(out_arg).write(out_bytes)
        return {"saved": out_arg.get("path"), "version": written.get("version"), "bytes": len(out_bytes)}
    # save next to source via notify — without file-out we only return size; agent should pass --out
    return {
        "bytes": len(out_bytes),
        "to": to,
        "hint": "Передайте --out путь для записи результата (file-out)",
        "source": meta["path"],
    }


def _starting_html() -> str:
    return """<!doctype html>
<html lang="ru"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Редактор запускается</title>
<style>
body{margin:0;font:14px/1.45 system-ui,sans-serif;background:var(--pulse-surface,#f6f7f9);color:var(--pulse-text,#1a1a1a);
display:flex;align-items:center;justify-content:center;min-height:100vh;padding:24px;text-align:center}
.box{max-width:28rem}.muted{color:var(--pulse-muted,#6b7280);font-size:13px;margin-top:8px}
</style></head>
<body><div class="box pl-empty">
  <div>Редактор запускается (1–3 минуты при первом старте)…</div>
  <div class="muted">OnlyOffice Docs поднимается в Docker. Страница обновится сама.</div>
</div>
<script>setTimeout(function(){location.reload()},5000)</script>
</body></html>"""


def _editor_html(api_js: str, config: dict, theme: str) -> str:
    cfg = json.dumps(config, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="ru" data-theme="{theme}"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Редактор</title>
<style>html,body,#place{{margin:0;height:100%;background:var(--pulse-surface,#fff)}}</style>
<script src="{api_js}"></script>
</head><body>
<div id="place"></div>
<script>
const cfg = {cfg};
function post(status, extra) {{
  const msg = Object.assign({{type: "pulse:file-status", status: status}}, extra || {{}});
  if (status === "saved") msg.at = new Date().toLocaleTimeString("ru-RU", {{hour:"2-digit", minute:"2-digit"}}).replace(":", ".");
  parent.postMessage(msg, location.origin);
}}
post("loading");
try {{
  const docEditor = new DocsAPI.DocEditor("place", Object.assign({{}}, cfg, {{
    events: {{
      onAppReady: function() {{ post("ready"); }},
      onDocumentStateChange: function(e) {{
        if (e && e.data) post("saving"); else post("saved");
      }},
      onError: function(e) {{
        post("error", {{message: (e && e.data) ? String(e.data) : "ошибка редактора"}});
      }},
      onRequestSaveAs: function(e) {{
        if (e && e.data && e.data.title) {{
          /* OnlyOffice save-as — core will surface via callback saved_as */
        }}
      }}
    }}
  }}));
  window.addEventListener("message", function(ev) {{
    if (ev.origin !== location.origin) return;
    if (ev.data && ev.data.type === "pulse:theme" && ev.data.theme) {{
      document.documentElement.setAttribute("data-theme", ev.data.theme);
    }}
  }});
}} catch (err) {{
  post("error", {{message: String(err)}});
}}
</script>
</body></html>"""
