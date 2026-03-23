# Sprint 6. Multi-case и Tenant Isolation

## Цель

Сделать изоляцию кейсов и tenant boundary проверяемым системным свойством, а не договоренностью на уровне кода.

## Ожидаемый результат спринта

- runtime context сбрасывается при переключении workspace;
- retrieval, prompt context, dialogue history, embeddings и question queue строго изолированы;
- UI и backend предотвращают cross-case contamination;
- isolation гарантируется regression-набором тестов.

## Задачи

### S6-T1. Реализовать workspace-scoped runtime context

Описание:
- вынести active organization, workspace, session, version state в единый runtime context;
- при смене workspace сбрасывать in-memory reasoning state, pending prompt cache и temporary grounding buffers;
- гарантировать, что один runtime context обслуживает только один workspace.

Критерии приемки:
- смена workspace выполняет hard reset reasoning context;
- предыдущий prompt/retrieval state не переживает switch;
- active session перепривязывается только к новому workspace.

### S6-T2. Зафиксировать organization-scoped и workspace-scoped namespaces

Описание:
- retrieval chunks, embeddings, question queue, dialogue sessions и governance reads работают в namespace tenant + workspace;
- любые shared caches и background workers должны учитывать namespace в ключах;
- запретить cross-workspace relation и retrieval joins.

Критерии приемки:
- ни один backend query не читает case data без фильтра по `organization_id` и `workspace_id`;
- кеши и индексы не переиспользуются между workspace;
- worker jobs не конфликтуют по namespace.

### S6-T3. Реализовать anti-contamination validator и guards

Описание:
- проверять, что answer grounding, citations, prompt fragments и lineage references принадлежат активному workspace;
- предусмотреть расширение validator contract на будущие decision entities: `DecisionOption`, `DecisionRecord`, `DecisionEvidenceLink`, historical pattern refs;
- блокировать mixed-context payload до возврата в UI;
- логировать contamination attempts как high-severity governance events.

Критерии приемки:
- любой reference из чужого workspace переводит ответ в `block`;
- contamination фиксируется в audit trail;
- validator работает и для ordinary answers, и для model update responses;
- contract validator допускает дальнейшее расширение на decision-wave без смены security semantics;
- extensibility contract задокументирован и покрыт unit test на plugin point для decision entities.

### S6-T4. Реализовать workspace switch UX safeguards

Описание:
- UI явно показывает `You are working in case X`;
- при переключении закрывает composer draft или помечает его as discarded/reconfirm required;
- не переносит timeline, evidence panel и open questions из предыдущего кейса.

Критерии приемки:
- пользователь визуально не может спутать активный кейс;
- stale UI data очищается на switch;
- pending re-entry status другого кейса не отображается в текущем.

### S6-T5. Собрать isolation regression suite

Описание:
- подготовить системный набор негативных сценариев на mixed retrieval, mixed prompt context, session bleed, question queue bleed, worker namespace collisions;
- добавить suite в CI как release-blocking gate с явной конфигурацией pre-merge и pre-release запусков.

Критерии приемки:
- любой обнаруженный cross-case leak падает как blocking regression;
- suite охватывает backend, worker и UI;
- результаты воспроизводимы на двух и более workspaces одной и разных организаций.
- есть явный CI deliverable: workflow/job configuration, которая запускает isolation suite автоматически.

## Тесты спринта

### Для S6-T1

- Runtime reset test: после switch workspace кеш prompt/retrieval очищен и не содержит старых identifiers.
- Session rebinding test: активная сессия после switch принадлежит только новому workspace.
- Version state reset test: `pending_version` и `affected_stages` предыдущего кейса не попадают в новый context.

### Для S6-T2

- Namespace query test: SQL/ORM smoke-набор подтверждает фильтрацию по tenant и workspace на всех case-bound repository calls.
- Cache key test: retrieval index и prompt cache включают `organization_id` и `workspace_id`.
- BM25 isolation regression test: section index одного workspace не может вернуть документы другого workspace даже при одинаковых section titles/query terms.
- Future vector isolation placeholder test: decision-pattern/vector retrieval layer обязан будет проходить аналогичную namespace-isolation проверку при включении в scope.
- Worker collision test: параллельные jobs разных workspaces не блокируют друг друга одним глобальным lock.

### Для S6-T3

- Contamination validator test: чужой claim/artifact ref в answer payload дает `block`.
- Prompt leak test: искусственная подмена supplementary fragment из другого workspace отсекается до LLM call или на validator step.
- Governance severity test: contamination incident пишет audit event с high-severity marker.
- Validator extension-point test: decision entity checker подключается без ослабления existing contamination semantics.

### Для S6-T4

- Frontend switch e2e test: пользователь переключает кейс и видит новую timeline, новую evidence panel и новый banner.
- Composer safety test: незавершенный draft при switch не отправляется в новый workspace silently.
- Reentry UI isolation test: status re-entry кейса A не отображается в кейсе B.

### Для S6-T5

- Cross-case regression pack: один и тот же пользователь с двумя кейсами не получает ни history bleed, ни retrieval bleed.
- Cross-tenant regression pack: пользователь из tenant A не может увидеть кейсы tenant B даже через прямые API вызовы.
- Release gate test: isolation suite обязателен для merge/release pipeline.
- CI wiring test: workflow действительно запускает suite на pull request и перед релизом, а не существует только как локальный script.
