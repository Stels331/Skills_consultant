---
id: case_20260317_001__characterization_passport
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
created_at: 2026-03-17T18:50:06.894529+00:00
updated_at: 2026-03-17T19:00:07.321321+00:00
---
На основе предоставленных аналитических срезов (Viewpoints) и слоев (Layers), я подготовил артефакты для этапа Характеризации. 

Главная проблема кейса — использование самого дорогого и критичного производственного ресурса (Технического директора) в качестве бесплатного калькулятора для неквалифицированных лидов. Это создает узкое горлышко (Weakest Link), убивает конверсию и ставит под угрозу производство.

Ниже представлены три обязательных файла для папки `characterization/`.

### 1. `characterization/characteristics_catalog.json`
Архив всех измеримых характеристик системы (CSLC-KERNEL).

```json
{
  "workspace_id": "case_20260317_001",
  "artifact_type": "characteristics_catalog",
  "valid_until": "2026-12-31",
  "characteristics": [
    {
      "id": "chr_time_to_quote",
      "name": "Time-to-Quote (TTQ) / Время оценки",
      "description": "Время, проходящее от момента получения заявки менеджером до выдачи коммерческого предложения клиенту.",
      "scale": "Часы",
      "polarity": "Чем меньше, тем лучше (Minimization)",
      "measurement_procedure": "Разница между timestamp создания лида в учетной системе (или получения email) и timestamp отправки КП клиенту. Вычисляется медиана (P50) и 90-й перцентиль (P90) за месяц."
    },
    {
      "id": "chr_standardization_ratio",
      "name": "Коэффициент стандартизации пресейла",
      "description": "Доля заявок, которые могут быть рассчитаны менеджером по продажам автономно (без привлечения ТД) с помощью прайс-листа или калькулятора.",
      "scale": "Проценты (%)",
      "polarity": "Чем больше, тем лучше (Maximization)",
      "measurement_procedure": "(Количество заявок, рассчитанных без ТД / Общее количество поступивших заявок) * 100."
    },
    {
      "id": "chr_quote_conversion_rate",
      "name": "Конверсия из Оценки в Договор",
      "description": "Процент заявок, по которым была произведена оценка, перешедших в стадию подписанного договора и запуска в производство.",
      "scale": "Проценты (%)",
      "polarity": "Чем больше, тем лучше (Maximization)",
      "measurement_procedure": "(Количество подписанных договоров / Количество выданных КП) * 100 за когорту (например, за месяц)."
    },
    {
      "id": "chr_cost_of_failed_quote",
      "name": "Стоимость мертвого пресейла (OPEX Bleed)",
      "description": "Прямые финансовые потери на оплату времени ТД, потраченного на расчет заявок, которые не конвертировались в сделки.",
      "scale": "Денежные единицы (UAH/USD)",
      "polarity": "Чем меньше, тем лучше (Minimization)",
      "measurement_procedure": "Среднее время ТД на 1 оценку (в часах) * Часовая ставка ТД * Количество отказов за период."
    },
    {
      "id": "chr_td_context_switches",
      "name": "Частота прерываний ТД (Context Switching)",
      "description": "Количество раз в день, когда ТД отвлекается от производственных задач на вопросы продаж.",
      "scale": "Количество прерываний / день",
      "polarity": "Чем меньше, тем лучше (Minimization)",
      "measurement_procedure": "Самозапись ТД (тайм-трекер) или подсчет количества прямых обращений/сообщений от менеджеров по продажам в рабочее время."
    },
    {
      "id": "chr_production_kpi_health",
      "name": "Выполнение производственного плана",
      "description": "Текущий KPI Технического директора по объему и качеству выпущенной продукции.",
      "scale": "Проценты (%) от плана",
      "polarity": "Чем больше, тем лучше (Maximization)",
      "measurement_procedure": "Данные из производственных отчетов (План/Факт)."
    }
  ]
}
```

### 2. `characterization/parity_plan.json`
Условия честного сравнения (Parity) текущего состояния (As-Is) и любых предлагаемых решений (To-Be), например, внедрения CPQ-калькулятора или найма сметчика.

```json
{
  "workspace_id": "case_20260317_001",
  "artifact_type": "parity_plan",
  "valid_until": "2026-12-31",
  "comparison_windows": {
    "baseline_period": "Последние 3 месяца (исторические данные)",
    "evaluation_period": "1 месяц после внедрения изменений"
  },
  "budgets_and_constraints": {
    "implementation_time_budget": "Не более 14 дней на изменение процесса (например, создание Excel-калькулятора или изменение регламента).",
    "financial_budget": "Сравниваемые решения не должны превышать стоимость найма 1 junior-сметчика (или стоимости лицензии простой CRM/CPQ) за квартал.",
    "td_time_budget": "На внедрение решения ТД может потратить не более 10 часов суммарно (на выгрузку алгоритмов расчета для калькулятора)."
  },
  "normalization_factors": [
    "Сравнивать конверсию можно только при сопоставимом объеме входящего трафика лидов (±15%).",
    "Сравнивать производственные KPI ТД можно только при отсутствии форс-мажоров на производстве (поломки магистрального оборудования, не зависящие от ТД)."
  ]
}
```

### 3. `characterization/characterization_passport.json`
Паспорт индикаторизации с выделением Слабого Звена (WLNK) и защитой от Reward Hacking (Anti-Goodhart).

```json
{
  "workspace_id": "case_20260317_001",
  "artifact_type": "characterization_passport",
  "valid_until": "2026-12-31",
  "weakest_link_wlnk": {
    "component": "Когнитивный ресурс Технического директора (ТД)",
    "description": "ТД является абсолютным бутылочным горлышком (SPOF). Пропускная способность всей компании по генерации выручки равна пропускной способности ТД по расчету смет.",
    "failing_indicator": "chr_time_to_quote (Текущее значение: 7-10 дней, что фатально для рынка)"
  },
  "portfolio": {
    "optimization_targets": [
      {
        "id": "chr_standardization_ratio",
        "rationale": "Главный рычаг расшивки горлышка. Передача расчета типовых заказов (цель: >50%) в отдел продаж мгновенно разгрузит ТД."
      },
      {
        "id": "chr_time_to_quote",
        "rationale": "Прямое устранение клиентского трения (Adoption Friction). Цель: снижение с 7-10 дней до 24-48 часов."
      }
    ],
    "hard_constraints": [
      {
        "id": "chr_production_kpi_health",
        "rationale": "Любые изменения в пресейле не должны обрушить основное производство. ТД должен выполнять план."
      },
      {
        "id": "chr_quote_conversion_rate",
        "rationale": "Защита от 'мусорных' быстрых оценок. Оценки должны быть точными и в рынке."
      }
    ],
    "risk_signals": [
      {
        "id": "chr_td_context_switches",
        "rationale": "Сигнализирует о том, что регламент нарушается, и сейлзы продолжают дергать ТД в обход новых правил."
      }
    ]
  },
  "anti_goodhart_analysis": [
    {
      "target": "Снижение Time-to-Quote (chr_time_to_quote)",
      "hack_risk": "Spiteful Quoting (Заградительные оценки). ТД или Сейлз, чтобы уложиться в SLA 24 часа, начнут выдавать оценки 'на глаз' с завышением цены в 2-3 раза, чтобы покрыть все риски без детального просчета.",
      "mitigation": "Жесткий мониторинг `chr_quote_conversion_rate`. Если скорость оценки растет, а конверсия падает до нуля — метрика хакнута. Оценка ради оценки не имеет смысла."
    },
    {
      "target": "Рост Коэффициента стандартизации (chr_standardization_ratio)",
      "hack_risk": "Сейлзы начнут 'натягивать' сложные кастомные заказы на стандартный прайс-лист/калькулятор, чтобы быстрее продать и получить бонус, игнорируя технологические ограничения.",
      "mitigation": "Введение этапа 'Технический акцепт' (Technical Gate) перед запуском в производство. Если сейлз продал нереализуемый по стандарту продукт, бонус аннулируется, а сделка отменяется."
    }
  ]
}
```
