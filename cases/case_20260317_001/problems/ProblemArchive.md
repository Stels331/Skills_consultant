---
id: case_20260317_001__problem_archive
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
created_at: 2026-03-17T18:53:51.574656+00:00
updated_at: 2026-03-17T18:53:51.574656+00:00
---
---
id: case_20260317_001__problem_portfolio
artifact_type: problem_portfolio
stage: problem_formation
state: draft
parent_refs: ["characterization/characterization_passport.json", "characterization/indicator_set.md"]
valid_until: 2026-12-31
owner_role: problem_architect
---

# Портфель Проблем (Problem Portfolio)

## Вертикальная трассировка системного разрыва (Vertical Traceability Gap)
- **Стратегия и Бизнес-модель:** Компания теряет потенциальную выручку и несет прямые убытки (OPEX Bleed) из-за фатального клиентского трения (ожидание КП 7-10 дней).
- **Функциональная модель:** Отсутствует функция преквалификации лидов и автономного расчета типовых заказов. Производственный поток и поток пресейла слиты в один.
- **Размещение (Компонентная структура):** Отсутствует инструмент (CPQ/калькулятор/прайс-лист), позволяющий отвязать расчет от носителя уникальных знаний.
- **Распределение ролей:** Менеджеры по продажам выполняют роль "маршрутизаторов", а Технический директор (ТД) принудительно исполняет роль "бесплатного сметчика", что блокирует его основную роль — управление производством.

## Выбранные Goldilocks-проблемы
Из множества возможных проблем (от "уволить ТД" до "купить дорогую ERP") выбраны две взаимосвязанные проблемы, находящиеся в зоне ближайшего развития компании:

1. **PRB-001: Делегирование типовой оценки (Decoupling Standard Quoting)** — Расшивка узкого горлышка через передачу расчетов на уровень отдела продаж.
2. **PRB-002: Внедрение барьера преквалификации (Pre-qualification Gate)** — Остановка OPEX Bleed через фильтрацию нецелевого трафика до привлечения ТД.

