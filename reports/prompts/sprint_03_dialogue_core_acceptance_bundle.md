# Acceptance Bundle: SPRINT_03_DIALOGUE_CORE

## Sprint State

```json

{
  "current_sprint": "SPRINT_03_DIALOGUE_CORE",
  "status": "awaiting_acceptance",
  "attempt": 1,
  "last_commit": "not-created (local changes ready for manual review)",
  "codex_summary_path": "reports/tests/sprint_03_dialogue_core_codex_summary_attempt_1.md",
  "test_report_path": "reports/tests/sprint_03_dialogue_core_test_report_attempt_1.md",
  "acceptance_notes_path": null
}

```

## Acceptance Prompt

# Manual Acceptance Prompt

Ты выполняешь ручную приемку текущего спринта.

Проверь только текущий спринт:

- `Current sprint`: `SPRINT_03_DIALOGUE_CORE`
- `Sprint spec`: `TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE/SPRINTS_DETAILED/SPRINT_03_DIALOGUE_CORE.md`
- `Current status`: `awaiting_acceptance`
- `Attempt`: `1`
- `Codex summary`: `reports/tests/sprint_03_dialogue_core_codex_summary_attempt_1.md`
- `Test report`: `reports/tests/sprint_03_dialogue_core_test_report_attempt_1.md`

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
# Acceptance Result: SPRINT_03_DIALOGUE_CORE

Decision: accept
```

или

```md
# Acceptance Result: SPRINT_03_DIALOGUE_CORE

Decision: changes requested

Findings:
- ...
- ...
```

После этого зафиксируй решение через `accept-sprint` или `request-changes`.

## Sprint Spec Path

TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE/SPRINTS_DETAILED/SPRINT_03_DIALOGUE_CORE.md

## Sprint Spec

# Sprint 3. Dialogue Backend MVP

## Цель

Собрать минимально полезный case-grounded dialogue backend: router, retrieval, grounding, provider abstraction, quota enforcement и session persistence.

## Ожидаемый результат спринта

- пользователь может задать вопрос по конкретному workspace;
- вопрос проходит classification before retrieval;
- retrieval строит grounding bundle из typed claims и supplementary text;
- BM25 section indexing появляется раньше embedding-based freshness machinery;
- provider/model выбираются через policy tiers;
- вызов LLM невозможен без quota preflight reservation;
- ответ и его grounding сохраняются в dialogue history.

## Задачи

### S3-T1. Реализовать dialogue sessions и message persistence

Описание:
- хранить `dialogue_sessions` и `dialogue_messages` с `organization_id`, `workspace_id`, `created_by_user_id`;
- поддержать session creation, append message, load history;
- привязать ответ к `workspace_version` и `graph_version`.

Критерии приемки:
- история сессии загружается только для активного workspace;
- каждое сообщение имеет actor, type и version binding;
- cross-workspace reuse одной session невозможен.

### S3-T2. Реализовать `QuestionRouter`

Описание:
- классификация в `constraint_query`, `problem_query`, `solution_query`, `report_query`, `evidence_query`, `clarification_needed`, `clarification_provided`;
- confidence score и safe fallback;
- вход `clarification_provided` не идет в retrieval.

Критерии приемки:
- router использует общий enum/contract, а не свободные строки;
- low-confidence route безопасно деградирует в `evidence_query` или `clarification_needed`;
- ordinary questions и model updates разделены на входе.

### S3-T3. Реализовать graph-first retrieval и dialogue projection

Описание:
- основной retrieval читает graph-native claims по `question_class`;
- добавляет support chains и signal types;
- формирует rank по relevance внутри текущего workspace.

Критерии приемки:
- retrieval строго workspace-scoped;
- `typed_claims` являются primary grounding;
- для `0` релевантных typed claims ordinary answer не строится.

### S3-T4. Реализовать section indexing и BM25 supplementary retrieval

Описание:
- индексировать markdown artifacts по section-level `SectionDoc`;
- хранить `artifact_type`, `stage`, `epistemic_status`, `source_refs`;
- использовать BM25 только как supplementary retrieval при недостатке typed context.

Критерии приемки:
- индекс строится по секциям, а не по целому файлу;
- BM25 не подменяет graph-first retrieval;
- text fragments всегда помечены как supplementary only.
- BM25 index физически и логически namespace-scoped по `organization_id` и `workspace_id`.

### S3-T5. Реализовать `GroundingBundle` и prompt builder

Описание:
- объединить `typed_claims`, `text_fragments`, `workspace_id`, `graph_version`, `workspace_version`;
- в prompt явно разделить `VERIFIED CLAIMS` и `SUPPORTING TEXT`;
- включить FPF guardrails и response contract.

Критерии приемки:
- prompt не смешивает typed claims и free-text fragments;
- version metadata входит в grounding bundle;
- prompt builder не пропускает данные из другого workspace.

### S3-T6. Реализовать embedding lifecycle foundation

Описание:
- `embedding_jobs`, stale/fresh revision markers, source revision tracking;
- active retrieval set переключается только после успешного пересчета;
- подготовить очереди и фоновые джобы для будущего embedding-aware retrieval и freshness controls.

Критерии приемки:
- изменение claim или artifact создает embedding job;
- stale chunks не используются как active retrieval set;
- worker безопасно повторяет failed job.

### S3-T7. Реализовать `LLMProviderAdapter`, routing policy tiers и quota preflight

Описание:
- единый adapter для direct mode и optional gateway mode;
- tiers `cheap`, `balanced`, `premium`;
- budget profiles `economy`, `standard`, `premium`, `strict_cap`;
- `QuotaEnforcementService` резервирует usage до внешнего provider call.

Критерии приемки:
- provider меняется конфигурацией, а не переписыванием orchestration logic;
- escalation `cheap -> balanced -> premium` ограничена policy;
- provider call без успешного reservation блокируется.

## Тесты спринта

### Для S3-T1

- Session repository test: создание сессии и последовательная запись сообщений сохраняют actor/type/version fields.
- Isolation test: загрузка history по session из другого workspace возвращает access error.
- Version binding test: ответ хранит `workspace_version_id` и `graph_version`, соответствующие моменту генерации.

### Для S3-T2

- Router unit test: покрыть все question classes валидными примерами.
- Low-confidence fallback test: неоднозначный вопрос уходит в безопасный fallback, а не в узкий domain route.
- Clarification path test: `clarification_provided` не вызывает retrieval service.

### Для S3-T3

- Retrieval integration test: `constraint_query` достает `decision_constraint` и поддерживающую цепочку фактов.
- Zero typed claims test: отсутствие релевантных claims возвращает `needs_clarification` или `insufficient_modeled_evidence`.
- Workspace isolation test: claims из другого workspace никогда не попадают в result set.

### Для S3-T4

- Section indexing test: один markdown с несколькими секциями индексируется как несколько `SectionDoc`.
- BM25 scope test: поиск ограничен `workspace_id`.
- BM25 namespace test: индексы разных `organization_id/workspace_id` физически не переиспользуются между кейсами.
- Supplementary-only test: text fragments помечаются так, чтобы prompt builder не воспринимал их как verified claims.

### Для S3-T5

- Grounding bundle contract test: bundle проходит schema validation и содержит version fields.
- Prompt composition test: prompt включает `VERIFIED CLAIMS`, `SUPPORTING TEXT`, `EPISTEMIC RULES`.
- Leak prevention test: попытка подмешать fragment другого workspace отбрасывается guard-логикой.

### Для S3-T6

- Embedding job creation test: изменение claim/artifact создает job и новую revision.
- Active set switch test: retrieval chunks меняются на свежую ревизию только после успешного job completion.
- Retry test: failed embedding job можно безопасно повторить без удвоения active chunks.

### Для S3-T7

- Adapter contract test: direct mode и gateway mode возвращают единый normalized response shape.
- Policy mapping test: task class и risk level выбирают корректный tier по policy.
- Quota preflight test: при отсутствии quota reservation provider call не выполняется.
- Escalation ceiling test: после `premium` дополнительный retry запрещен.

## Codex Summary Path

reports/tests/sprint_03_dialogue_core_codex_summary_attempt_1.md

## Codex Summary

# Sprint 03 Codex Summary

- Добавлен dialogue backend модуль [app/canonical_db/dialogue_backend.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/app/canonical_db/dialogue_backend.py) с session/message persistence, `QuestionRouter`, graph-first retrieval, BM25 section indexing, grounding bundle, prompt builder, embedding lifecycle, quota enforcement и provider adapter.
- Добавлена DB revision `20260322_0003_dialogue_backend` для retrieval/embedding freshness state.
- Обновлен runtime bundle, чтобы новые dialogue/retrieval репозитории были доступны через [app/canonical_db/runtime.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/app/canonical_db/runtime.py).
- Добавлен acceptance-level тестовый набор [tests/test_sprint_03_dialogue_core.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/tests/test_sprint_03_dialogue_core.py).
- Foundation regression в [tests/test_sprint_01_foundation.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/tests/test_sprint_01_foundation.py) обновлен под цепочку из трех alembic revisions.

## Test Report Path

reports/tests/sprint_03_dialogue_core_test_report_attempt_1.md

## Test Report

# Sprint 03 Test Report

Executed:

```bash
python3 -m unittest tests.test_sprint_03_dialogue_core
python3 -m unittest tests.test_sprint_01_foundation tests.test_sprint_02_auth_graph tests.test_sprint_03_dialogue_core
python3 -m py_compile app/canonical_db/domain.py app/canonical_db/dialogue_backend.py app/canonical_db/runtime.py tests/test_sprint_03_dialogue_core.py
```

Result:

- `tests.test_sprint_03_dialogue_core`: `7 tests`, `OK`
- `tests.test_sprint_01_foundation + tests.test_sprint_02_auth_graph + tests.test_sprint_03_dialogue_core`: `21 tests`, `OK`
- `py_compile`: `OK`

## Commit / Diff Context

not-created (local changes ready for manual review)

## Diff Hint

No commit recorded yet

## Acceptance Checklist

- Все обязательные задачи спринта закрыты.

- Критерии приемки спринта выполнены.

- Релевантные тесты запущены и результаты зафиксированы.

- Нет очевидного scope creep вне спринта.

- Оставшиеся ограничения и blockers описаны явно.
