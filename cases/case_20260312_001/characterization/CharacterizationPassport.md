---
id: case_20260312_001__characterization_passport
artifact_type: characterization_passport
stage: characterization
state: shaped
parent_refs: ["viewpoints/strategist.md", "viewpoints/analyst.md", "viewpoints/operator.md", "viewpoints/architect.md", "viewpoints/critic.md", "viewpoints/client.md"]
source_refs: ["viewpoints/conflicts_index.md:L1"]
evidence_refs: []
viewpoints: []
epistemic_status: observed
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: pass
violated_principles: []
next_expected_artifacts: ["problems/ProblemArchive.md"]
created_at: 2026-03-12T10:15:44.512050+00:00
updated_at: 2026-03-12T10:28:00.188559+00:00
---
Основываясь на предоставленных аналитических срезах и моделях слоев, я подготовил пакет артефактов для этапа Характеризации (папка `characterization/`). 

В основе проблемы лежит жесткое физическое ограничение (Weakest Link) — пропускная способность Технического директора (ТД), которая напрямую разрушает клиентский опыт (Time-to-Quote = 7-10 дней) и юнит-экономику пресейла.

Ниже представлены 3 обязательных файла в формате JSON.

### 1. `characterization/characteristics_catalog.json`
Архив всех измеримых характеристик системы (CSLC-KERNEL), переведенных из абстрактных жалоб в конкретные шкалы.

```json
{
  "catalog_id": "cat_case_20260312_001",
  "version": "1.0",
  "updated_at": "2026-03-12T12:00:00Z",
  "characteristics": [
    {
      "id": "CHR-01-TTQ",
      "name": "Time-to-Quote (Время оценки заявки)",
      "description": "Время от момента получения заявки Менеджером до отправки коммерческого предложения Клиенту.",
      "scale": "Рабочие часы",
      "polarity": "minimize",
      "measurement_procedure": "Выгрузка таймстемпов из почты/мессенджеров: (Время отправки КП) - (Время получения ТЗ от клиента). Расчет медианы и 90-го перцентиля.",
      "valid_until": "2026-12-31"
    },
    {
      "id": "CHR-02-AUTONOMY",
      "name": "Коэффициент автономности продаж (Sales Autonomy Rate)",
      "description": "Доля заявок, которые Менеджер по продажам оценивает самостоятельно, без привлечения Технического директора.",
      "scale": "Проценты (%)",
      "polarity": "maximize",
      "measurement_procedure": "Отношение количества заявок, оцененных без ТД, к общему количеству поступивших заявок за месяц.",
      "valid_until": "2026-12-31"
    },
    {
      "id": "CHR-03-WASTE",
      "name": "Уровень мусорной нагрузки (Waste Ratio)",
      "description": "Доля времени Технического директора, потраченная на оценку заявок, которые в итоге не конвертировались в договор.",
      "scale": "Проценты (%)",
      "polarity": "minimize",
      "measurement_procedure": "Когортный анализ: (Кол-во часов ТД на отказные заявки) / (Общее кол-во часов ТД на пресейл) * 100.",
      "valid_until": "2026-12-31"
    },
    {
      "id": "CHR-04-CONVERSION",
      "name": "Конверсия из Оценки в Договор (Quote-to-Order)",
      "description": "Процент заявок, по которым была произведена оценка и в итоге подписан контракт.",
      "scale": "Проценты (%)",
      "polarity": "maximize",
      "measurement_procedure": "Воронка продаж: (Кол-во подписанных договоров) / (Кол-во выданных оценок) * 100.",
      "valid_until": "2026-12-31"
    },
    {
      "id": "CHR-05-MARGIN",
      "name": "Фактическая маржинальность выполненных заказов",
      "description": "Реальная валовая маржа по закрытым сделкам (защита от занижения цен при быстрой оценке).",
      "scale": "Проценты (%)",
      "polarity": "maximize",
      "measurement_procedure": "(Выручка по заказу - Фактическая производственная себестоимость) / Выручка * 100.",
      "valid_until": "2026-12-31"
    }
  ]
}
```

### 2. `characterization/parity_plan.json`
Условия честного сравнения (Parity Plan). Любое предлагаемое решение (нанять сметчика, внедрить ERP, сделать Excel-калькулятор, изменить KPI) должно оцениваться в единых координатах затрат и ограничений.

```json
{
  "parity_id": "parity_case_20260312_001",
  "context": "Сравнение архитектурных и организационных решений для расшивки узкого места пресейла.",
  "evaluation_window": {
    "duration_months": 3,
    "description": "Решение должно показать измеримый результат (снижение TTQ) не позднее чем через 3 месяца после старта внедрения."
  },
  "budgets_and_limits": {
    "capex_limit_usd": 5000,
    "capex_description": "Максимальный бюджет на разовую разработку (IT-инструменты, калькуляторы, консалтинг по оцифровке прайса).",
    "opex_limit_usd_per_month": 1500,
    "opex_description": "Максимальное увеличение ежемесячных расходов (например, найм выделенного пресейл-инженера или подписка на SaaS)."
  },
  "hard_constraints": [
    {
      "constraint": "Zero Production Disruption",
      "description": "Внедрение решения не должно требовать остановки производства или снижения текущих KPI Технического директора по объему выпуска."
    },
    {
      "constraint": "Bus Factor > 1",
      "description": "Решение не должно создавать новую единую точку отказа (например, замена ТД на одного уникального сметчика без оцифровки методологии не принимается)."
    }
  ]
}
```

### 3. `characterization/characterization_passport.json`
Паспорт характеризации. Фиксирует текущее слабое звено, выбранные цели оптимизации и жестко прописывает риски Reward Hacking'а (Анти-Гудхарт).

```json
{
  "passport_id": "pass_case_20260312_001",
  "workspace_id": "case_20260312_001",
  "status": "active",
  "weakest_link_wlnk": {
    "component": "Когнитивная и временная емкость Технического директора (Узел F1.2 / Allocation: ТД).",
    "failure_mode": "Синхронная блокировка потока продаж. ТД физически не способен обрабатывать 100% нефильтрованных лидов без ущерба для производства, что приводит к задержке в 7-10 дней и потере клиентов."
  },
  "indicator_portfolio": {
    "optimization_targets": [
      {
        "characteristic_id": "CHR-01-TTQ",
        "current_state": "168-240 часов (7-10 дней)",
        "target_state": "< 24 часов для 80% заявок",
        "rationale": "Прямое устранение трения принятия (Adoption Friction) для клиента."
      },
      {
        "characteristic_id": "CHR-02-AUTONOMY",
        "current_state": "0%",
        "target_state": "> 70%",
        "rationale": "Отчуждение экспертизы. Единственный способ масштабировать продажи — дать Менеджеру инструмент самостоятельной оценки типовых заказов."
      }
    ],
    "anti_goodhart_protocol": {
      "description": "Защита от хакинга метрик (Reward Hacking) при попытке быстро снизить Time-to-Quote.",
      "identified_risks": [
        {
          "hack_scenario": "Менеджер по продажам или ТД начинают оценивать заявки 'на глаз' за 5 минут, систематически занижая себестоимость, чтобы быстрее выдать КП и закрыть сделку.",
          "system_damage": "Рост продаж при отрицательной маржинальности. Кассовый разрыв и убытки при выполнении контрактов."
        },
        {
          "hack_scenario": "ТД заставляют отвечать за 24 часа штрафами. Он бросает производство, станки простаивают, срываются сроки по уже оплаченным заказам.",
          "system_damage": "Коллапс производственного ядра, штрафы от текущих клиентов."
        }
      ],
      "hard_constraints_acceptance": [
        {
          "characteristic_id": "CHR-05-MARGIN",
          "threshold": "Не ниже исторической нормы (например, > 25%).",
          "action_if_violated": "Остановка продаж по новым алгоритмам, аудит калькулятора/прайса."
        },
        {
          "metric": "Выполнение плана производства (KPI ТД)",
          "threshold": "Не ниже 95% от плана.",
          "action_if_violated": "Снятие с ТД обязанности по оценке заявок до стабилизации производства."
        }
      ],
      "risk_signals_monitoring": [
        {
          "characteristic_id": "CHR-04-CONVERSION",
          "warning_trigger": "Резкое падение конверсии при быстром ответе (означает, что ТД начал закладывать 'заградительные' цены x2, чтобы от него отстали)."
        }
      ]
    }
  }
}
```
