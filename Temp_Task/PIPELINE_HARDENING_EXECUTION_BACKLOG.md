# Pipeline Hardening Execution Backlog

## 1. Цель

Разложить внедрение архитектурных исправлений по pipeline на атомарные задачи без скрытых зависимостей.

Задачи ориентированы на:

- убрать ложные `BLOCK` / `DEGRADE`;
- синхронизировать генераторы и contracts;
- ввести pre-gate checks до записи артефакта на диск;
- не ломать текущий pipeline при частичном внедрении.

## 2. Правила внедрения

- Каждый шаг должен быть завершен кодом, smoke test и короткой проверкой результата.
- Skills обновляются вместе с соответствующим runner, не после него.
- Изменение `SelectedProblemCard` делается атомарно вместе с parser-логикой в `epistemic_graph.py`.
- Numeric sanitation не должен молча переписывать утверждения в trusted artifact.
- Полный regression suite запускается в конце, но baseline и smoke tests обязательны раньше.

## 3. Backlog

### Task 00. Baseline фиксация

Цель:
- зафиксировать исходную точку до изменений.

Файлы:
- без изменений в коде

Действия:
- прогнать текущий baseline test set;
- сохранить список failing/passing tests;
- зафиксировать текущие проблемы по кейсу `case_20260321_001`.

Минимальная проверка:
- `tests.test_solution_factory_pipeline`
- `tests.test_reporting_gate_policy`
- `tests.test_contract_validator`

Ожидаемый результат:
- есть точка сравнения до внедрения.

---

### Task 01. Убрать outer fenced wrapper из реальных LLM outputs

Цель:
- не допускать `PLACEHOLDER_CONTENT` из-за ` ```markdown ` как внешней оболочки.

Файлы:
- [app/llm/client.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышение/Skills/FPF-skill_2/electronic_consultant_v3/app/llm/client.py)

Действия:
- добавить `_strip_fenced_wrapper()`;
- вызывать только для real LLM modes;
- `local` mode не трогать.

Smoke check:
- synthetic test: полный fenced markdown unwrap;
- nested internal fenced block не ломается.

Ожидаемый результат:
- raw artifact body больше не попадает в gate как placeholder только из-за внешней fenced оболочки.

---

### Task 02. Исправить short-id mismatch в parity artifacts

Цель:
- убрать ложный fallback в parity/tradeoff из-за `sol_01` vs `sol_01_full_name`.

Файлы:
- [app/pipeline/parity_tradeoff.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышение/Skills/FPF-skill_2/electronic_consultant_v3/app/pipeline/parity_tradeoff.py)

Действия:
- добавить `_build_prefix_map()`;
- добавить `_expand_short_ids()`;
- вызывать expansion до `_validate_parity_artifact()`;
- разворачивать только однозначные префиксы.

Smoke check:
- `sol_01 -> sol_01_micro_batch_barter` при однозначном match;
- неоднозначный prefix не заменяется;
- уже полные ids не портятся.

Ожидаемый результат:
- `Parity Report failed validation` не возникает на корректных short-id outputs.

---

### Task 03. Baseline smoke после Tasks 01-02

Цель:
- убедиться, что formatting/id fixes не сломали pipeline.

Файлы:
- без новых изменений

Проверка:
- `tests.test_solution_factory_pipeline`
- прицельный запуск parity-related tests

Ожидаемый результат:
- formatting/id fixes подтверждены до более глубоких изменений.

---

### Task 04. Ввести section pre-gate layer

Цель:
- проверять required sections до `write_markdown_artifact()`, а не только в orchestrator gate.

Файлы:
- [app/pipeline/section_contract_guard.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышение/Skills/FPF-skill_2/electronic_consultant_v3/app/pipeline/section_contract_guard.py)

Действия:
- реализовать `check_required_sections()`;
- реализовать `repair_sections_with_retry()` или аналог;
- outcome должен быть structured:
  - `clean`
  - `repaired`
  - `degraded`
  - `failed`

Smoke check:
- known-good body -> `clean`;
- missing sections + repair success -> `repaired`;
- missing sections without repair -> `degraded` or `failed`.

Ожидаемый результат:
- появляется единый pre-gate contract layer для runner-ов.

---

### Task 05. Viewpoint runner + viewpoint skills

Цель:
- убрать narrative-only outputs в viewpoints;
- привести generated viewpoint artifacts к контракту секций.

Файлы:
- [app/pipeline/viewpoint_runner.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышение/Skills/FPF-skill_2/electronic_consultant_v3/app/pipeline/viewpoint_runner.py)
- relevant files in [.agent/skills/](/Users/stas/Documents/Системное%20Мышление/Системное%20мышение/Skills/FPF-skill_2/electronic_consultant_v3/.agent/skills)

Действия:
- подключить `section_contract_guard`;
- section contract брать из viewpoint contract;
- добавить repair retry;
- одновременно обновить viewpoint SKILL files на exact required sections.

Smoke check:
- runner не пишет viewpoint artifact без required sections;
- real LLM prompt и contract-shaped output согласованы.

Ожидаемый результат:
- `viewpoints` перестают валиться на `CONTRACT_REQUIRED_SECTION_MISSING`.

---

### Task 06. Characterization runner + characterization skill

Цель:
- убрать свободный narrative в `CharacterizationPassport`;
- синхронизировать runner, skill и contract.

Файлы:
- [app/pipeline/characterization.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышение/Skills/FPF-skill_2/electronic_consultant_v3/app/pipeline/characterization.py)
- related characterization skill file(s)

Действия:
- подключить `section_contract_guard`;
- добавить retry/repair;
- обновить skill под required sections.

Smoke check:
- missing required sections не проходят до disk write.

Ожидаемый результат:
- `characterization` не деградирует только из-за отсутствующих contract sections.

---

### Task 07. Atomic refactor: SelectedProblemCard typed sections

Цель:
- развести `facts`, `chr_targets`, `derived_thresholds`, `anti_goodhart_conditions`, `hypotheses_to_validate`;
- не сломать extraction claims в graph.

Файлы:
- [app/pipeline/problem_factory.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышение/Skills/FPF-skill_2/electronic_consultant_v3/app/pipeline/problem_factory.py)
- [contracts/selected_problem_card.contract.json](/Users/stas/Documents/Системное%20Мышление/Системное%20мышение/Skills/FPF-skill_2/electronic_consultant_v3/contracts/selected_problem_card.contract.json)
- [app/pipeline/epistemic_graph.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышение/Skills/FPF-skill_2/electronic_consultant_v3/app/pipeline/epistemic_graph.py)
- related problem skill file(s)

Действия:
- менять эти 3 компонента только в одном шаге;
- обновить extraction logic на новые section names;
- обновить skill prompt на typed output discipline.

Smoke check:
- `SelectedProblemCard.md` пишется с новой typed structure;
- `extract_claims_from_artifact()` создает claims из новых секций;
- graph не остается пустым молча.

Ожидаемый результат:
- `CHR_TARGET_AND_DERIVED_BLURRED` исчезает как class of defect.

---

### Task 08. Smoke tests после Tasks 04-07

Цель:
- не накапливать сломанные стадии до конца большой серии изменений.

Проверка:
- section guard unit tests
- viewpoint runner smoke
- characterization smoke
- problem_factory + epistemic_graph smoke

Ожидаемый результат:
- pre-gate layer подтвержден по стадиям, где он уже внедрен.

---

### Task 09. Numeric claim detection layer

Цель:
- перестать silently пропускать незаякоренные числа;
- не переписывать trusted artifact body без явного downgrade path.

Файлы:
- [app/pipeline/epistemic_sanitizer.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышение/Skills/FPF-skill_2/electronic_consultant_v3/app/pipeline/epistemic_sanitizer.py) или существующий sanitizer-layer

Действия:
- реализовать detection first;
- optional repair retry;
- controlled softening только как fallback/degraded path;
- не использовать silent mutation по умолчанию.

Smoke check:
- numeric findings детектятся локально;
- clearly anchored numeric claims не помечаются как invalid;
- fallback path помечает artifact как degraded если needed.

Ожидаемый результат:
- `UNANCHORED_NUMERIC_CLAIMS` переводится из “поздний сюрприз на gate” в управляемый pre-gate signal.

---

### Task 10. Integrate numeric detection into Solution Portfolio + Reporting

Цель:
- убрать типичный `DEGRADE` в `solution_factory` и `reporting` от numerics;
- не потерять traceability.

Файлы:
- [app/pipeline/solution_portfolio.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышение/Skills/FPF-skill_2/electronic_consultant_v3/app/pipeline/solution_portfolio.py)
- [app/pipeline/reporting.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышение/Skills/FPF-skill_2/electronic_consultant_v3/app/pipeline/reporting.py)
- relevant skills

Действия:
- встроить detection/retry layer;
- при необходимости писать degraded metadata, а не молча переписывать как trusted body;
- обновить prompts одновременно с кодом.

Smoke check:
- solution/reporting artifacts не дают ложный numeric degrade на типовом кейсе;
- problematic numerics still traceable.

Ожидаемый результат:
- `solution_factory` и `reporting` перестают регулярно деградировать из-за raw numeric prose.

---

### Task 11. Final regression suite

Цель:
- подтвердить, что pipeline целиком стал стабильнее и contract-aware.

Проверка:
- полный regression suite
- case-based run на `case_20260321_001`

Критерии приемки:
- `layers` не блокируется из-за outer fenced wrapper;
- `viewpoints` не блокируются из-за missing required sections;
- `characterization` не деградирует из-за contract mismatch;
- `problem_factory` не смешивает CHR-targets и derived thresholds;
- `solution_factory` не падает в false parity fallback на short ids;
- `reporting` не деградирует на ложных unanchored numeric claims;
- orchestrator gate становится финальным guardrail, а не первым местом обнаружения структурного мусора.

## 4. Suggested PR / Commit slicing

### PR 1
- Task 01
- Task 02
- Task 03

### PR 2
- Task 04
- Task 05

### PR 3
- Task 06

### PR 4
- Task 07
- Task 08

### PR 5
- Task 09
- Task 10

### PR 6
- Task 11

## 5. Главное правило

Нельзя одновременно менять:

- section contracts,
- extraction logic,
- skill prompts,
- downstream readers

без промежуточной smoke-проверки.

Для этого проекта безопаснее серия маленьких синхронизированных шагов, чем один большой “архитектурный рефакторинг”.
