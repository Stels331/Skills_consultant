# Typization Stage Specification (v1)

## Purpose
Перевести распарсенный текст кейса в типизированные артефакты:
- atomic claims;
- typed entities;
- relation skeleton;
- candidate type proposals.

## Registry model (dynamic)
Реестр типов в папке `Type/` состоит из 4 файлов:
- `known_types.json` — утвержденные типы для продакшн-типизации.
- `candidate_types.json` — временные типы, предложенные на основе новых сущностей.
- `mapped_types.json` — карта нормализации candidate -> known.
- `deprecated_types.json` — выведенные из использования типы.

## Typization pipeline
1. Input: `cases/<workspace_id>/parsed/*.txt`
2. Segment text into atomic statements (line-based for v1).
3. Classify statement kind:
- `FACT`: содержит цифры/даты/единицы измерения/мощности.
- `INTERPRETATION`: остальное.
4. Extract entities by keyword dictionaries and aliases from `known_types.json`.
5. Enforce single-type assignment per entity in current pass.
6. Propose candidate types for unmatched domain terms.
7. Emit artifacts:
- `extracted/entities.json`
- `extracted/claims.json`
- `extracted/relations.json`
- `analysis/typed_entities.json`
- `analysis/type_proposals.json`

## Output contracts
- `entities.json`: unique entity records (`entity_id`, `name`, `type`, `aliases`).
- `claims.json`: claim records (`claim_id`, `text`, `kind`, `entity_ids`).
- `typed_entities.json`: normalized type assignments + confidence.
- `type_proposals.json`: candidate proposals with rationale.

## Non-goals (v1)
- Full semantic parsing and deep syntax trees.
- Automatic ontology governance decisions.
- Cross-document coreference beyond simple normalization.
