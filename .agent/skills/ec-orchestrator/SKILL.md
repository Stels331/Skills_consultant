---
name: ec-orchestrator
description: Главный навык Электронного Консультанта (v3). Координирует жизненный цикл кейса, стадии обработки и вызывает локальные скрипты воркспейса. С этого навыка начинается базовая работа с проектом.
---

# Электронный Консультант: Оркестратор

Этот навык управляет общим процессом консалтингового кейса в системе "Электронный Консультант".

## Архитектурные Принципы FPF
- Источник истины — внешний `Case Workspace` на файловой системе (markdown/json). Не держите состояние в памяти!
- **B.5.1 Explore → Shape → Evidence → Operate**: Работа идет через управляемый цикл: извлечение -> типизация -> фабрика проблем -> фабрика решений.
- **A.4 Temporal Duality & Open-Ended Evolution Principle**: Изменения фиксируются инкрементально. Пользуйтесь контрольными точками.
- Одноранговая независимая модульность: этапы можно повторять.

## Инструкции (WorkFlow)

1. **Инициализация Воркспейса**: 
   - Клиент начинает кейс. Запусти: `python3 scripts/workspace_cli.py --project-root . create`
   - Переведи статус в ACTIVE: `python3 scripts/workspace_cli.py --project-root . set-state <case_id> ACTIVE --reason "Start"`

2. **Работа по стадиям (Operating Flow)**: 
   Каждый кейс проходит этапы. Если этап не пройден, используй специализированные навыки:
   - *Parsing и Extraction*: Используй навык `ec-extraction`. (Цель: получить entities, claims, source_manifest).
   - *Typization*: Запускай скрипт типизации: `python3 scripts/run_typization.py <case_id>`. Если скрипт просит дообучения, используй FPF-Gate на *A.11 Ontological Parsimony*.
   - *Characterization*: Используй навык `ec-characterization` (определение индикаторов и шкал).
   - *Problem Space Formation / Фабрика Проблем*: Используй навык `ec-problem-factory`.
   - *Solution Space / Фабрика Решений*: Используй навык `ec-solution-factory`.

3. **Сохранение и Проверка (Harnessing)**:
   - После каждого значимого изменения (этапа), сделай checkpoint:
     `python3 scripts/workspace_cli.py --project-root . checkpoint <case_id> --reason "completed stage X" --structural`
   - Проверяй консистентность артефактов схемами:  
     `python3 scripts/validate_workspace.py <case_id>`
   - Без прохождения валидации, этап считается *FPF-FAILED*.

4. **Завершение**: 
   - При завершении цикла "Оперирование" (разбора кейса) автоматически сгенерируй финальный отчет:
     1. Создай markdown файл отчета: `python3 scripts/generate_report.py <case_id>`
     2. Скомпилируй его в HTML: `quarto render cases/<case_id>/reports/final_report.qmd --to html`
     3. Выдай краткий финальный ответ пользователю и приложи ссылку на готовый отчет (`final_report.html`) и Evidence Graph (A.10).
