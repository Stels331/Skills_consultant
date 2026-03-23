# Codex Sprint Runbook

## Цель

Этот runbook задает простой рабочий процесс:

1. `Codex` выполняет только текущий спринт.
2. `Codex` сохраняет summary и test report.
3. Человек вручную принимает или отклоняет спринт по чеклисту.
4. Только после ручного `accept` выполняется переход к следующему спринту.

Автоматический loop orchestration и автоматический LLM-reviewer не используются.

## Артефакты

- state: [reports/sprint_state.json](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/reports/sprint_state.json)
- prompt template для `Codex`: [prompts/antigravity/codex_sprint_prompt.md](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/prompts/antigravity/codex_sprint_prompt.md)
- prompt template для ручной приемки: [prompts/antigravity/manual_acceptance_prompt.md](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/prompts/antigravity/manual_acceptance_prompt.md)
- orchestrator helper: [scripts/run_sprint_loop.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/scripts/run_sprint_loop.py)

Папки отчетов:

- `reports/tests/`
- `reports/reviews/`
- `reports/prompts/`

## Статусы

Поддерживаемые значения `status`:

- `ready`
- `in_progress`
- `awaiting_acceptance`
- `changes_requested`
- `accepted`
- `completed`

## Рабочий процесс

### 1. Инициализация

```bash
python3 scripts/run_sprint_loop.py init
```

### 2. Проверить текущий спринт

```bash
python3 scripts/run_sprint_loop.py status
```

### 3. Подготовить prompt и bundle для Codex

```bash
python3 scripts/run_sprint_loop.py prepare-codex
python3 scripts/run_sprint_loop.py build-bundle --agent codex
```

или:

```bash
make sprint-prepare-codex
make sprint-build-codex-bundle
```

Важно:

- эти команды только готовят артефакты;
- они не означают, что разработка уже реально началась;
- статус спринта после них не должен меняться на `in_progress`.

### 4. Явно зафиксировать старт работы

```bash
python3 scripts/run_sprint_loop.py start-codex
```

Только после этого спринт считается реально начатым и получает статус `in_progress`.

### 5. Выполнить спринт через Codex

Bundle отдается в `Codex` вручную или через внешний UI/CLI.

После завершения должны быть готовы:

- summary file
- test report file
- commit hash, если commit удалось создать

### 6. Зафиксировать результат Codex

```bash
python3 scripts/run_sprint_loop.py codex-done \
  --commit "<commit-or-not-created>" \
  --summary-file reports/tests/sprint_01_summary.md \
  --test-report reports/tests/sprint_01_tests.md
```

После этого статус станет `awaiting_acceptance`.

### 7. Собрать acceptance pack для ручной проверки

```bash
python3 scripts/run_sprint_loop.py build-bundle --agent acceptance
```

или:

```bash
make sprint-build-acceptance-bundle
```

Acceptance bundle включает:

- sprint spec
- текущий state
- summary
- test report
- commit/diff hint
- чеклист для ручной приемки

### 8. Ручная приемка

Проверяющий вручную выносит решение:

- `accept`
- `changes requested`

Решение фиксируется файлом в `reports/reviews/`, например:

`reports/reviews/sprint_01_manual_acceptance.md`

### 9. Зафиксировать ручную приемку

Если спринт принят:

```bash
python3 scripts/run_sprint_loop.py accept-sprint \
  --notes-file reports/reviews/sprint_01_manual_acceptance.md
```

Если спринт не принят:

```bash
python3 scripts/run_sprint_loop.py request-changes \
  --notes-file reports/reviews/sprint_01_manual_acceptance.md
```

После этого собери новый `codex` bundle и начинай следующую итерацию вручную.

### 10. Перейти к следующему спринту

```bash
python3 scripts/run_sprint_loop.py advance
```

Переход возможен только из состояния `accepted`.

## Команды

Через `Makefile`:

```bash
make sprint-status
make sprint-prepare-codex
make sprint-build-codex-bundle
make sprint-build-acceptance-bundle
```

Через `scripts/run_sprint_loop.py`:

- `init`
- `status`
- `set-sprint`
- `prepare-codex`
- `start-codex`
- `build-bundle --agent codex`
- `build-bundle --agent acceptance`
- `codex-done`
- `accept-sprint`
- `request-changes`
- `advance`

## Принцип

- код пишет `Codex`
- решение о приемке принимает человек
- `run_sprint_loop.py` хранит только контекст спринта и артефакты
- автоматический loop и автоматический reviewer считаются отключенными
