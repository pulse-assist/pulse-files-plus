# PulseFiles+ — заметки для агента

Плагин дополняет раздел «Файлы» Пульса редактором OnlyOffice. Контракт ядра ≥ **1.2**
(`embed`, `services`, `files:open`, билеты, `/plugin-apps/…`).

- Меню и отдельные страницы UI **нет** — всё в панели «Файлов».
- Сервис `docs` — OnlyOffice; страница `/editor` отдаётся runtime и грузит `api.js` через
  `{PULSE_PLUGIN_APP_PATH}/s/docs/…`.
- Не логируй содержимое документов и JWT.
- Спайк OnlyOffice под префиксом: ядро шлёт `X-Forwarded-Host` с путём при `proxy.host_with_prefix`.

См. README.md и INSTALL.md.
