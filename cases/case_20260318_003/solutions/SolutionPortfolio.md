---
id: case_20260318_003__solution_portfolio
artifact_type: solution_portfolio
stage: solution_factory
state: shaped
parent_refs: ["problems/SelectedProblemCard.md", "problems/ComparisonAcceptanceSpec.md"]
source_refs: ["problems/ComparisonAcceptanceSpec.md:L1"]
evidence_refs: ["problems/SelectedProblemCard.md:L1"]
viewpoints: []
epistemic_status: inferred
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: pass
violated_principles: []
next_expected_artifacts: ["solutions/ParityReport.md", "solutions/ConflictRecords.md"]
created_at: 2026-03-18T20:41:30.259329+00:00
updated_at: 2026-03-18T20:48:50.584442+00:00
---
# Solution Space Meta-Model

## Weak Intervention Class
- principle: Класс weak-interventions описывает минимально достаточные и обратимые меры, которые меняют правила входа, фильтрацию, маршрутизацию или локальные роли без тяжелой перестройки архитектуры.
- purpose: represent a reusable intervention class, not a case-specific patch
- selection_rule: keep this class in the portfolio only if it adds a distinct pareto profile or a safer rollout path
- instances: sol_01_halt_deep_processing

## Medium Intervention Class
- principle: Класс medium-interventions описывает меры, которые частично отчуждают повторяемую экспертную функцию в метод, инструмент или отдельный операционный контур, но не требуют полной трансформации системы.
- purpose: represent a reusable intervention class, not a case-specific patch
- selection_rule: keep this class in the portfolio only if it adds a distinct pareto profile or a safer rollout path
- instances: sol_02_asynchronous_cyclogram_and_barter

## Strong Intervention Class
- principle: Класс strong-interventions описывает меры, которые меняют саму топологию системы, архитектурные границы, оргструктуру или бизнес-модель, когда локальные меры уже недостаточны.
- purpose: represent a reusable intervention class, not a case-specific patch
- selection_rule: keep this class in the portfolio only if it adds a distinct pareto profile or a safer rollout path
- instances: sol_03_toll_processing_outsourcing

## sol_00_status_quo
- type: process
- assurance_level: high
- intervention_force: none
- relevance_basis: baseline
- сценарий_"не_делать_ничего"._выполнение_прямого_распоряжения_правления: физический запуск всех участков завода (лесопилка, сушильные камеры, термомодификация) одновременно в конфигурации "как есть", с питанием от коммерческой электросети и складированием отходов на территории.
- *финансовый_ущерб: Отрицательная юнит-экономика. Стоимость коммерческой электроэнергии для сушки и термомодификации превысит маржинальность готового продукта. Сжигание остатка ликвидности (Cash Runway) произойдет менее чем за 2 месяца.
- *инфраструктурный_ущерб: Пиковое потребление превысит 700 kW, что приведет к регулярным отключениям подстанции, порче оборудования и браку в сушильных камерах (нарушение температурного режима).
- *экологический_ущерб: Накопление отходов (+25 m³/сутки) приведет к затовариванию площадки за 10-14 дней, остановке лесопилки и вероятным экологическим штрафам.
- требуемые_компетенции: Отсутствуют.
- ожидаемый_радиус_поражения_(blast_radius): Тотальный. Банкротство предприятия в течение 1-2 месяцев.
- риски: 100% вероятность кассового разрыва и остановки производства по техническим и экологическим причинам.

## sol_01_halt_deep_processing
- type: policy
- assurance_level: high
- intervention_force: weak
- relevance_basis: pareto_relevant
- nqd_explore/exploit: Exploit работающей лесопилки; Explore рынка сбыта сырой доски.
- временный_отказ_от_глубокой_переработки._сушильные_камеры_и_установки_термомодификации_консервируются_до_решения_проблемы_с_генератором._завод_работает_исключительно_как_лесопилка,_выпуская_сырую_премиум: доску. Отходы (опил, щепа) отдаются бесплатно или с минимальной доплатой местным пеллетным заводам на условиях самовывоза "день в день".
- b2b: продажи (поиск покупателей на сырую доску).
- *стратегия: Временный отказ от позиционирования "производитель термодерева".
- *процесс: Остановка 60% производственной цепочки.
- *ит: Не требует изменений (достаточно базового учета в 1С/Excel).
- снижение_выручки_из: за низкой маржинальности сырой доски (однако юнит-экономика становится положительной за счет обнуления затрат на э/э для сушки).

## sol_02_asynchronous_cyclogram_and_barter
- type: process
- assurance_level: medium
- intervention_force: medium
- relevance_basis: rollout_relevant
- nqd_explore/exploit: Exploit разницы в тарифах и асинхронности; Explore реального энергопотребления сушилок.
- *процесс: Лесопилка работает только в дневную смену (08:00-20:00). Сушильные камеры и термомодификация включаются только в ночную смену (20:00-08:00), используя льготный ночной тариф на электроэнергию (снижение OPEX).
- *ит: Требуется внедрение системы контроля расписания и энергопотребления.
- *отходы: Заключение бартерного контракта с ближайшей муниципальной котельной или производством: мы поставляем им 25 m³/сутки отходов бесплатно, они компенсируют часть наших затрат на электроэнергию или берут на себя всю логистику вывоза (обнуление `CHR-02-WASTE-ACCUM`).
- инженер: энергетик (расчет точных пусковых токов и профиля потребления).
- *бизнес_процесс: Переход на сменный/ночной график работы, изменение системы оплаты труда рабочих.
- зависимость_от_контрагента_по_вывозу_отходов: срыв графика вывоза остановит дневную смену.

## sol_03_toll_processing_outsourcing
- type: architecture
- assurance_level: low
- intervention_force: strong
- relevance_basis: rollout_relevant
- nqd_explore/exploit: Exploit собственного бренда и лесопилки; Explore рынка давальческих услуг (Toll processing).
- *процесс: Лесопилка пилит доску. Вместо сушки на своих мощностях, сырая доска отправляется на завод-партнер, у которого есть избыточные мощности сушильных камер и дешевая тепловая энергия (например, собственная ТЭЦ на биотопливе). Партнер сушит доску до < 8-10% влажности и возвращает нам.
- *отходы: Отходы лесопиления прессуются в брикеты на дешевом б/у прессе (CAPEX < $15k) и продаются, превращаясь из проблемы в источник покрытия логистических затрат.
- *ит: компонент:* Внедрение системы Supply Chain Management (SCM) для трекинга партий доски на стороне подрядчика и контроля процента брака при сторонней сушке.
- *стратегия: Виртуализация производства. Завод становится "управляющей компанией" с частичным собственным производством.
- *архитектура: Физические сушильные камеры на нашей территории выводятся из эксплуатации и могут быть сданы в аренду/проданы для пополнения Cash Runway.
- *assurance_level_low: Нет гарантий, что в радиусе рентабельной логистики есть партнер с нужным качеством сушки (требует срочного NQD-поиска).
- увеличение_длительности_производственного_цикла_(lead_time)_из: за логистического плеча.

