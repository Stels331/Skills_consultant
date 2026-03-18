---
id: case_20260312_001__char_card__decision_confidence_score
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
created_at: 2026-03-12T10:17:52.150908+00:00
updated_at: 2026-03-12T10:17:52.150908+00:00
---
Основываясь на вашей задаче (фокус на индикаторе `decision_confidence_score` в роли цели оптимизации), я подготовил пакет артефактов для этапа Характеризации. 

В данном кейсе мы рассматриваем систему принятия решений (например, скоринг, автоматическая маршрутизация или AI-ассистент), где **Слабым Звеном (Weakest Link)** является низкая уверенность системы, что приводит к массовому ручному вмешательству (Manual Override) и разрушает ценность автоматизации.

Ниже представлены 3 обязательных файла в формате JSON, которые необходимо поместить в папку `characterization/`.

### 1. `characterization/characteristics_catalog.json`
Архив измеримых характеристик (CSLC-KERNEL). Мы переводим абстрактное понятие "качество решений" в многомерное пространство метрик.

```json
{
  "catalog_id": "cat_decision_opt_001",
  "workspace_id": "case_20260312_001",
  "version": "1.0",
  "updated_at": "2023-10-25T10:00:00Z",
  "characteristics": [
    {
      "id": "CHR-01-CONF",
      "name": "Decision Confidence Score (Уверенность в решении)",
      "description": "Метрика уверенности алгоритма или оператора в правильности предлагаемого решения до его фактического исполнения.",
      "scale": "Проценты (%)",
      "polarity": "maximize",
      "measurement_procedure": "Агрегация вероятностных оценок (probability scores) из логов Decision Engine по всем транзакциям за сутки. Расчет медианы и доли решений с уверенностью >80%.",
      "valid_until": "2024-12-31"
    },
    {
      "id": "CHR-02-AUTO",
      "name": "Automation Rate (Уровень автоматизации/Straight-Through Processing)",
      "description": "Доля решений, которые были приняты и исполнены системой автоматически, без ручного подтверждения (Manual Override).",
      "scale": "Проценты (%)",
      "polarity": "maximize",
      "measurement_procedure": "(Кол-во автоматически исполненных задач) / (Общее кол-во задач) * 100.",
      "valid_until": "2024-12-31"
    },
    {
      "id": "CHR-03-ERR",
      "name": "Error Rate (Доля ошибочных решений)",
      "description": "Процент решений, которые впоследствии были признаны ошибочными (апелляции, возвраты, сбои).",
      "scale": "Проценты (%)",
      "polarity": "minimize",
      "measurement_procedure": "Ретроспективный анализ: (Кол-во отмененных/исправленных решений) / (Общее кол-во принятых решений) * 100.",
      "valid_until": "2024-12-31"
    },
    {
      "id": "CHR-04-COV",
      "name": "Coverage (Охват оценки)",
      "description": "Доля входящих запросов, для которых система вообще смогла сформировать гипотезу решения (не выдала ошибку 'Недостаточно данных').",
      "scale": "Проценты (%)",
      "polarity": "maximize",
      "measurement_procedure": "(Кол-во запросов с сформированным скором) / (Общее кол-во входящих запросов) * 100.",
      "valid_until": "2024-12-31"
    },
    {
      "id": "CHR-05-TTD",
      "name": "Time-to-Decision (Время на принятие решения)",
      "description": "Время от поступления вводных данных до фиксации итогового решения.",
      "scale": "Секунды",
      "polarity": "minimize",
      "measurement_procedure": "Разница таймстемпов: (Время записи решения в БД) - (Время получения payload'а).",
      "valid_until": "2024-12-31"
    }
  ]
}
```

### 2. `characterization/parity_plan.json`
Условия честного сравнения (Parity Plan). Любые инициативы по повышению `decision_confidence_score` (внедрение LLM, доп. интеграции данных, изменение UI для оператора) должны оцениваться в единых рамках.

```json
{
  "parity_id": "parity_decision_opt_001",
  "workspace_id": "case_20260312_001",
  "context": "Сравнение решений для повышения уверенности и автоматизации принятия решений.",
  "evaluation_window": {
    "duration_months": 2,
    "description": "Решение должно выйти на целевые показатели уверенности (Confidence Score) в течение 2 месяцев после деплоя."
  },
  "budgets_and_limits": {
    "capex_limit_usd": 15000,
    "capex_description": "Бюджет на разработку, дообучение моделей или интеграцию новых поставщиков данных.",
    "opex_limit_usd_per_month": 3000,
    "opex_description": "Максимальные ежемесячные затраты на API (например, OpenAI/Anthropic) или вычислительные мощности."
  },
  "hard_constraints": [
    {
      "constraint": "Strict Latency Limit",
      "description": "Медианное время принятия решения (CHR-05-TTD) не должно превышать 5 секунд, чтобы не блокировать синхронные процессы."
    },
    {
      "constraint": "Data Privacy Compliance",
      "description": "Запрещена отправка PII (персональных данных) в сторонние несертифицированные API для обогащения контекста."
    }
  ]
}
```

### 3. `characterization/characterization_passport.json`
Паспорт характеризации. Фиксирует слабое звено, цели и **Анти-Гудхарт протокол**, защищающий систему от "накрутки" уверенности.

```json
{
  "passport_id": "pass_decision_opt_001",
  "workspace_id": "case_20260312_001",
  "status": "active",
  "weakest_link_wlnk": {
    "component": "Модуль оценки (Decision Engine) / Оператор первой линии.",
    "failure_mode": "Хроническая нехватка контекста приводит к низкой уверенности (Confidence < 40%). Из-за этого система не рискует применять автоматические действия, перенаправляя 60%+ потока на ручной разбор, что создает бутылочное горлышко."
  },
  "indicator_portfolio": {
    "optimization_targets": [
      {
        "characteristic_id": "CHR-01-CONF",
        "current_state": "Медиана 38%",
        "target_state": "Медиана > 85%",
        "rationale": "Прямая метрика (optimization_goal), позволяющая разблокировать автоматическое исполнение задач."
      },
      {
        "characteristic_id": "CHR-02-AUTO",
        "current_state": "15%",
        "target_state": "> 60%",
        "rationale": "Бизнес-следствие роста уверенности: снижение нагрузки на экспертов."
      }
    ],
    "anti_goodhart_protocol": {
      "description": "Защита от Reward Hacking'а при максимизации Decision Confidence Score.",
      "identified_risks": [
        {
          "hack_scenario": "Калибровочный хак (Calibration Hack): Разработчики искусственно смещают пороги вероятности в модели (например, умножают все скоры на 1.5), чтобы система рапортовала о высокой уверенности.",
          "system_damage": "Система начинает автоматически принимать неверные решения с 'высокой уверенностью'. Резкий рост убытков от ошибок (False Positives)."
        },
        {
          "hack_scenario": "Черри-пикинг (Cherry-picking): Система начинает отбрасывать (reject) любые мало-мальски сложные заявки еще до этапа скоринга, оценивая только тривиальные случаи.",
          "system_damage": "Confidence Score равен 99%, но 80% заявок вообще не обрабатываются и падают в бэклог."
        }
      ],
      "hard_constraints_acceptance": [
        {
          "characteristic_id": "CHR-03-ERR",
          "threshold": "Не более 2.5% (исторический бейзлайн).",
          "action_if_violated": "Немедленный откат модели/алгоритма на предыдущую версию. Запрет на автоматическое исполнение."
        },
        {
          "characteristic_id": "CHR-04-COV",
          "threshold": "Не ниже 95%.",
          "action_if_violated": "Штрафные санкции к метрике уверенности (расчет Confidence Score с учетом необработанных заявок как 0%)."
        }
      ],
      "risk_signals_monitoring": [
        {
          "characteristic_id": "CHR-05-TTD",
          "warning_trigger": "Рост времени ответа > 3 секунд (сигнализирует о том, что для повышения уверенности алгоритм начал делать слишком много тяжелых запросов к БД)."
        }
      ]
    }
  }
}
```
