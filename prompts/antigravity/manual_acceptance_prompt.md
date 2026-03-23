# Manual Acceptance Prompt

Ты выполняешь ручную приемку текущего спринта.

Проверь только текущий спринт:

- `Current sprint`: `{{CURRENT_SPRINT}}`
- `Sprint spec`: `{{SPRINT_SPEC_PATH}}`
- `Current status`: `{{STATE_STATUS}}`
- `Attempt`: `{{ATTEMPT}}`
- `Codex summary`: `{{CODEX_SUMMARY_PATH}}`
- `Test report`: `{{TEST_REPORT_PATH}}`

## Что проверить

- Все обязательные задачи спринта действительно выполнены.
- Критерии приемки закрыты без очевидных пробелов.
- Релевантные тесты запущены и отражены в test report.
- Нет явного выхода за scope спринта.
- Все ограничения, blocker'ы и допущения зафиксированы явно.

## Формат результата

Сохрани результат ручной проверки в markdown-файл в `reports/reviews/`.

Структура результата:

```md
# Acceptance Result: {{CURRENT_SPRINT}}

Decision: accept
```

или

```md
# Acceptance Result: {{CURRENT_SPRINT}}

Decision: changes requested

Findings:
- ...
- ...
```

После этого зафиксируй решение через `accept-sprint` или `request-changes`.
