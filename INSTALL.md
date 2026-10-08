# Установка PulseFiles+

1. Предупреди владельца: плагин **встраивается в «Файлы» с его правами** (`embed`) и запускает
   OnlyOffice в Docker: ~3 ГБ на диске, 3 ГБ памяти, первый запуск 1–3 минуты. Ставь только после «да».

2. Установка:

   ```bash
   pulse plugins install https://github.com/pulse-assist/pulse-files-plus --grant embed,services,files:open,notify
   ```

   Дождись `status: running` и сервиса `docs` — `running` (`pulse plugins get files-plus`).
   Нет Docker / мало памяти — в журнале будет понятная ошибка.

3. Проверка:

   ```bash
   pulse files-plus status
   pulse files create "" "Проверка.docx" --template files-plus:docx
   pulse files-plus text "Проверка.docx"
   ```

   Попроси владельца открыть файл в «Файлах», дописать строку, дождаться «Сохранено», снова `text`.

4. Расскажи: клик по `.docx` — редактор в панели; «Создать ▾» — Документ/Таблица/Презентация;
   агенты — `text` / `convert`; на телефоне — просмотр; Community — до ~20 одновременных соединений.
