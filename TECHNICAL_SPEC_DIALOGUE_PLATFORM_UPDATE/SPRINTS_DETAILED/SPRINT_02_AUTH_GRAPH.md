# Sprint 2. Auth, Tenant Layer, Claim Graph

## Цель

Ввести tenant-aware account layer и перевести case model на claims/projections в БД, чтобы следующий спринт мог безопасно строить диалог на каноническом графе.

## Ожидаемый результат спринта

- пользователь может зарегистрироваться, войти и переключать организации;
- authorization проверяет tenant boundary до workspace boundary;
- claims, claim versions и relations живут в БД с immutable history;
- validators и projections читают canonical DB read model;
- embedding lifecycle готовит retrieval freshness после изменений модели.

## Задачи

### S2-T1. Реализовать auth/session foundation

Описание:
- registration, login, logout, password reset hooks;
- session storage и проверка статуса пользователя;
- `email_verified_at`, `last_login_at`, базовые account settings;
- подготовить точки расширения под external auth providers, не делая их обязательными.

Критерии приемки:
- новый пользователь может создать аккаунт и войти;
- заблокированный пользователь не получает session;
- session инвалидируется при logout.

### S2-T2. Реализовать organizations, memberships и role model

Описание:
- CRUD для organizations;
- invite/join flow для membership;
- роли `organization_owner`, `organization_admin`, `workspace_editor`, `workspace_viewer`;
- organization switcher backend contract.

Критерии приемки:
- пользователь видит только свои организации;
- смена active organization меняет контекст всех tenant-aware запросов;
- роль ограничивает допустимые операции.

### S2-T3. Ввести tenant-aware authorization guards

Описание:
- API guards сначала проверяют membership в организации, затем права на workspace;
- исключить доступ по знанию `workspace_id`;
- подготовить policy checks для dialogues, claims, artifacts, question queue и governance events.

Критерии приемки:
- все case-bound endpoints требуют tenant context;
- cross-tenant доступ блокируется до выполнения бизнес-логики;
- unauthorized access логируется как security event.

### S2-T4. Канонизировать claim graph и version history

Описание:
- нормализовать graph-native types: `source_fact`, `derived_metric`, `decision_constraint`, `normative_target`, `interpretation`, `hypothesis`;
- добавить immutable `claim_versions`;
- реализовать `claim_relations` и базовые relation types;
- определить conflict и duplicate handling.

Критерии приемки:
- обновление claim создает новую версию, а не затирает старую;
- relation graph собирается без обращения к файловому traversal;
- true contradiction и duplicate cluster различаются явно.

### S2-T5. Реализовать projections и migration validators на DB read model

Описание:
- materialize dialogue-friendly и validator-friendly projections из canonical БД;
- перевести validators на repositories/projections вместо прямого чтения файлов;
- обеспечить детерминированную пересборку projections.

Критерии приемки:
- validators работают без legacy graph traversal;
- projections можно пересчитать из БД с тем же результатом;
- projection metadata хранит version/freshness context.

### S2-T6. Реализовать embedding lifecycle foundation

Описание:
- `embedding_jobs`, stale/fresh revision markers, source revision tracking;
- active retrieval set переключается только после успешного пересчета;
- подготовить очереди и фоновые джобы для будущего retrieval слоя.

Критерии приемки:
- изменение claim или artifact создает embedding job;
- stale chunks не используются как active retrieval set;
- worker безопасно повторяет failed job.

## Тесты спринта

### Для S2-T1

- Auth integration test: регистрация создает `users` и `user_profiles`, login выдает session, logout ее закрывает.
- Negative auth test: неверный пароль и `status != active` не создают session.
- Session expiry test: просроченная session отвергается middleware.

### Для S2-T2

- Membership flow test: owner создает организацию, приглашает пользователя, после join membership получает корректную роль.
- Organization switch test: active organization меняется без доступа к чужим данным.
- Role matrix test: `workspace_viewer` не может редактировать claims, `organization_admin` может управлять membership.

### Для S2-T3

- Tenant security test: пользователь из организации A не может читать workspace организации B даже при корректном `workspace_id`.
- Guard coverage test: все case-bound endpoints требуют membership check.
- Audit test: попытка unauthorized access пишет governance/security event.

### Для S2-T4

- Claim versioning test: update claim создает запись в `claim_versions` и обновляет active pointer.
- Relation integrity test: relation не может связывать claims из разных workspaces.
- Conflict test: противоречащие claims создают `conflict_case`, а семантические дубли — `duplicate_claim_cluster`.

### Для S2-T5

- Projection rebuild test: полный rebuild projections из БД дает стабильный результат на одном и том же dataset.
- Validator parity test: migrated validator outcome совпадает с legacy validator на контрольном наборе кейсов.
- Freshness test: после обновления claim старый projection помечается stale до пересборки.

### Для S2-T6

- Embedding job creation test: изменение claim/artifact создает job и новую revision.
- Active set switch test: retrieval chunks меняются на свежую ревизию только после успешного job completion.
- Retry test: failed embedding job можно безопасно повторить без удвоения active chunks.
