# PulseFiles+

Офисные документы в разделе «Файлы» платформы [Пульс](https://github.com/pulse-assist/pulse):
`.docx` / `.xlsx` / `.pptx` (и ODF) открываются в панели просмотра через **OnlyOffice Docs Community**.

Плагин — дополнение к «Файлам», не отдельный сайт. Браузер ходит только на адрес Пульса
(`/plugin-apps/files-plus/…`). Поддомены и правка DNS/Caddy не нужны.

## Права

- `embed` — встраивание в «Файлы» с сессией владельца (ставьте только если доверяете)
- `files:open` — билеты на открытый файл
- `services` — контейнер OnlyOffice (~3 ГБ RAM, ~3 ГБ диска)
- `notify` — сигнал при сохранении копией / ошибке

## Лицензии

- Код плагина — **MIT**
- OnlyOffice Docs Community — **AGPL v3**; образ берётся с Docker Hub по digest, плагином не
  модифицируется и не распространяется

## Разработка

```bash
pip install -r backend/requirements-dev.txt
pulse-plugin check
pytest -q
```

Контракт ядра: [CONTRACT.md](https://github.com/pulse-assist/pulse-plugin-sdk/blob/main/CONTRACT.md) (≥1.2).
