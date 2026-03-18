---
id: case_20260317_001__char_card__decision_confidence_score
artifact_type: characteristic_card
stage: characterization
state: draft
parent_refs: ["characterization/CharacterizationPassport.md"]
source_refs: ["characterization/CharacterizationPassport.md:L1"]
evidence_refs: []
viewpoints: []
epistemic_status: observed
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: pending
violated_principles: []
next_expected_artifacts: ["problems/ProblemArchive.md"]
created_at: 2026-03-17T18:52:10.500082+00:00
updated_at: 2026-03-17T18:52:10.500082+00:00
---
На основе переданных данных и поставленной задачи (`task_type: build_characteristic_card`), я интегрировал показатель **Decision Confidence Score** в качестве цели оптимизации (`role: optimization_goal`) для текущего кейса. 

В контексте проблемы (Технический директор как узкое горлышко для пресейла), **Decision Confidence Score** интерпретируется как *уверенность менеджера по продажам в правильности самостоятельно рассчитанного КП* (без привлечения ТД). Если менеджеры не будут уверены в своих расчетах или новых инструментах (CPQ/калькуляторах), они продолжат саботировать процесс и "теневым" образом дергать ТД.

Ниже представлены обновленные артефакты для папки `characterization/`.

### 1. `characterization/characteristics_catalog.json`
Архив характеристик (CSLC-KERNEL) пополнен новой метрикой уверенности.

```json
{
  "workspace_id": "case_20260317_001",
  "artifact_type": "characteristics_catalog",
  "valid_until": "2026-12-31",
  "characteristics": [
    {
      "id": "chr_time_to_quote",
      "name": "Time-to-Quote (TTQ) / Время оценки",
      "description": "Время от получения заявки до выдачи коммерческого предложения клиенту.",
      "scale": "Часы",
      "polarity": "Чем меньше, тем лучше (Minimization)",
      "measurement_procedure": "Разница между timestamp создания лида и отправки КП. Вычисляется медиана (P50) и 90-й перцентиль (P90)."
    },
    {
      "id": "chr_standardization_ratio",
      "name": "Коэффициент стандартизации пресейла",
      "description": "Доля заявок, рассчитанных менеджером автономно (без ТД).",
      "scale": "Проценты (%)",
      "polarity": "Чем больше, тем лучше (Maximization)",
      "measurement_procedure": "(Количество заявок без ТД / Общее количество заявок) * 100."
    },
    {
      "id": "chr_decision_confidence_score",
      "name": "Decision Confidence Score (Уверенность в оценке)",
      "description": "Уровень субъективной уверенности менеджера по продажам в корректности сформированного КП и технической реализуемости проекта без проверки ТД.",
      "scale": "Баллы (1-10)",
      "polarity": "Чем больше, тем лучше (Maximization)",
      "measurement_procedure": "Обязательный self-report (опросник в CRM из 1 пункта) при переводе сделки на этап 'КП отправлено'. Альтернатива: автоматический скоринг полноты введенных данных в калькулятор."
    },
    {
      "id": "chr_quote_conversion_rate",
      "name": "Конверсия из Оценки в Договор",
      "description": "Процент оцененных заявок, перешедших в подписанный договор.",
      "scale": "Проценты (%)",
      "polarity": "Чем больше, тем лучше (Maximization)",
      "measurement_procedure": "(Количество договоров / Количество выданных КП) * 100 за когорту."
    },
    {
      "id": "chr_cost_of_failed_quote",
      "name": "Стоимость мертвого пресейла (OPEX Bleed)",
      "description": "Прямые потери на оплату времени ТД по неконвертированным заявкам.",
      "scale": "USD",
      "polarity": "Чем меньше, тем лучше (Minimization)",
      "measurement_procedure": "Среднее время ТД на 1 оценку * Часовая ставка ТД * Количество отказов."
    },
    {
      "id": "chr_td_context_switches",
      "name": "Частота прерываний ТД (Context Switching)",
      "description": "Количество отвлечений ТД на вопросы продаж в день.",
      "scale": "Количество прерываний / день",
      "polarity": "Чем меньше, тем лучше (Minimization)",
      "measurement_procedure": "Подсчет количества прямых обращений/сообщений от менеджеров в рабочее время."
    },
    {
      "id": "chr_production_kpi_health",
      "name": "Выполнение производственного плана",
      "description": "Текущий KPI ТД по объему и качеству выпущенной продукции.",
      "scale": "Проценты (%) от плана",
      "polarity": "Чем больше, тем лучше (Maximization)",
      "measurement_procedure": "Данные из производственных отчетов (План/Факт)."
    }
  ]
}
```

### 2. `characterization/parity_plan.json`
Условия честного сравнения (Parity) дополнены требованиями к замеру уверенности.

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
    "implementation_time_budget": "Не более 14 дней на изменение процесса.",
    "financial_budget": "Стоимость решения не превышает найм 1 junior-сметчика за квартал.",
    "td_time_budget": "На внедрение решения ТД может потратить не более 10 часов суммарно."
  },
  "normalization_factors": [
    "Сравнивать конверсию можно только при сопоставимом объеме входящего трафика (±15%).",
    "Сравнивать производственные KPI ТД можно только при отсутствии форс-мажоров на производстве.",
    "Замер Decision Confidence Score 'До' (As-Is) должен проводиться на тех же менеджерах, что и 'После' (To-Be), чтобы исключить искажения из-за разного уровня квалификации сотрудников."
  ]
}
```

### 3. `characterization/characterization_passport.json`
Паспорт с выделением Слабого Звена (WLNK) и проработанным Anti-Goodhart анализом для нового индикатора.

```json
{
  "workspace_id": "case_20260317_001",
  "artifact_type": "characterization_passport",
  "valid_until": "2026-12-31",
  "weakest_link_wlnk": {
    "component": "Когнитивный ресурс Технического директора (ТД)",
    "description": "ТД является абсолютным бутылочным горлышком (SPOF). Пропускная способность компании по генерации выручки ограничена его пропускной способностью по расчету смет.",
    "failing_indicator": "chr_time_to_quote (Текущее значение: 7-10 дней)"
  },
  "portfolio": {
    "optimization_targets": [
      {
        "id": "chr_standardization_ratio",
        "rationale": "Главный рычаг расшивки горлышка. Передача расчета типовых заказов в отдел продаж."
      },
      {
        "id": "chr_time_to_quote",
        "rationale": "Прямое устранение клиентского трения. Цель: снижение до 24-48 часов."
      },
      {
        "id": "chr_decision_confidence_score",
        "rationale": "Критическая метрика принятия (Adoption). Если менеджеры не уверены в своих расчетах, они будут саботировать регламент и продолжать отвлекать ТД."
      }
    ],
    "hard_constraints": [
      {
        "id": "chr_production_kpi_health",
        "rationale": "Изменения в пресейле не должны обрушить основное производство."
      },
      {
        "id": "chr_quote_conversion_rate",
        "rationale": "Защита от 'мусорных' оценок. Оценки должны быть точными и в рынке."
      }
    ],
    "risk_signals": [
      {
        "id": "chr_td_context_switches",
        "rationale": "Сигнализирует о теневом нарушении регламента (сейлзы дергают ТД в обход правил)."
      },
      {
        "id": "chr_cost_of_failed_quote",
        "rationale": "Показывает, не стали ли мы тратить еще больше денег на исправление ошибок после 'самостоятельных' оценок."
      }
    ]
  },
  "anti_goodhart_analysis": [
    {
      "target": "Снижение Time-to-Quote (chr_time_to_quote)",
      "hack_risk": "Spiteful Quoting (Заградительные оценки). Чтобы уложиться в SLA 24 часа, менеджеры начнут выдавать оценки 'на глаз' с завышением цены в 2-3 раза.",
      "mitigation": "Жесткий мониторинг `chr_quote_conversion_rate`. Если скорость растет, а конверсия падает — метрика хакнута."
    },
    {
      "target": "Рост Коэффициента стандартизации (chr_standardization_ratio)",
      "hack_risk": "Сейлзы начнут 'натягивать' сложные кастомные заказы на стандартный калькулятор ради бонуса за скорость, игнорируя технологические ограничения.",
      "mitigation": "Введение этапа 'Technical Gate' перед производством. За продажу нереализуемого продукта бонус аннулируется."
    },
    {
      "target": "Рост Decision Confidence Score (chr_decision_confidence_score)",
      "hack_risk": "Blind Confidence (Слепая самоуверенность). Менеджеры будут ставить 10/10 'на автомате', чтобы CRM пропустила КП клиенту, не вникая в суть расчета и снимая с себя ответственность.",
      "mitigation": "Введение 'Налога на самоуверенность' (Confidence Penalty). Если менеджер ставит 10/10, но расчет оказывается убыточным на этапе производства, штраф удваивается по сравнению с честной оценкой 'низкой уверенности' (которая легально ушла бы на аудит к ТД)."
    }
  ]
}
```
