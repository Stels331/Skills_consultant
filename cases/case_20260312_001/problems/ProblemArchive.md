---
id: case_20260312_001__problem_archive
artifact_type: problem_archive
stage: problem_factory
state: draft
parent_refs: ["characterization/CharacterizationPassport.md", "characterization/IndicatorSet.md", "viewpoints/conflicts_index.md"]
source_refs: ["characterization/CharacterizationPassport.md:L1"]
evidence_refs: []
viewpoints: []
epistemic_status: observed
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: pending
violated_principles: []
next_expected_artifacts: ["problems/ProblemPortfolio.md"]
created_at: 2026-03-12T10:19:19.996003+00:00
updated_at: 2026-03-12T10:19:19.996003+00:00
---
# Problem Spec 1: Разрыв синхронной зависимости Продаж и Производства

**Симптом:** Time-to-Quote составляет 7-10 дней. Автономность менеджера = 0%. Вся логика оценки заперта в голове ТД (Bus Factor = 1).

**Задача:** Предложить организационно-технический механизм, который позволит Менеджеру по продажам самостоятельно формировать КП для типовых заявок, не отвлекая ТД от производства.

**Приёмочные ограничения (Acceptance Criteria):**
1. **Целевые метрики:** 
   - CHR-02-AUTONOMY (Автономность продаж): рост с 0% до > 70%.
   - CHR-01-TTQ (Время оценки): снижение до < 24 часов для 80% заявок.
2. **Бюджетные лимиты (Parity Plan):** 
   - CAPEX (разовые затраты на разработку/консалтинг) <= $5000.
   - OPEX (ежемесячные затраты, найм, SaaS) <= $1500/мес.
3. **Анти-Гудхарт (Hard Constraints):**
   - CHR-05-MARGIN: Фактическая маржа по сделкам, оцененным без ТД, не должна упасть ниже исторической нормы (> 25%).
   - CHR-06-PROD_KPI: Выполнение плана производства ТД не ниже 95%.

**Метод верификации:** 
А/В тестирование или когортный анализ на периоде 3 месяца. Сравнение маржинальности когорты заявок, оцененных по новому механизму, с исторической когортой, оцененной лично ТД.

**Срок годности проблемы:** До 31.12.2026.

