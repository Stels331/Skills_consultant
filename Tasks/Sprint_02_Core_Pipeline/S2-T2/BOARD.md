# S2-T2 — Extraction + Typization + Glossary binding (общее описание)

**Для борди:** короткий опис задачі для швидкого ознайомлення.


**Приоритет:** Must


## Цель
Извлечь сущности/claims/relations и связать термины с глоссарием в рамках контекста.

## Что делаем
- Extraction в `entities.json`, `claims.json`, `relations.json`, `unknowns.json`.
- Типизацию сущностей по EC_LAYER_TYPING_MODEL.
- Glossary binding через `EC_GLOSSARY` (Term ID + Context + Kind).

## Критерий успеха
Сырые высказывания превращаются в типизированную, проверяемую модель утверждений.
