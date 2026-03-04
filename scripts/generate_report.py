import os
import sys
import json
from pathlib import Path
import argparse

def read_file(path: Path) -> str:
    if not path.exists():
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def read_json(path: Path) -> list:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def generate_report(case_dir: Path, output_file: Path):
    print(f"Генерация отчета для кейса: {case_dir.name}")
    
    # 1. Краткое общее описание (raw/case_input.md)
    raw_input_path = case_dir / "raw" / "case_input.md"
    raw_input = read_file(raw_input_path)
    
    # 2. Вопросы (extracted/unknowns.json)
    unknowns_path = case_dir / "extracted" / "unknowns.json"
    unknowns = read_json(unknowns_path)
    
    unknowns_md = ""
    for u in unknowns:
        unknowns_md += f"- **{u.get('type', 'Unknown')}**: {u.get('description', '')}\n"
    if not unknowns_md:
        unknowns_md = "*Немає запитань для прояснення.*"

    # 3. Анализ и проблемы (problems/*.md)
    problems_dir = case_dir / "problems"
    problems_md = ""
    if problems_dir.exists():
        for p_file in problems_dir.glob("*.md"):
            content = read_file(p_file)
            # Берем первые несколько строк или весь файл
            problems_md += f"### {p_file.name}\n\n{content}\n\n"
    if not problems_md:
        problems_md = "*Проблем не виявлено.*"

    # 4. Предлагаемые решения (decisions/*.md)
    decisions_dir = case_dir / "decisions"
    decisions_md = ""
    if decisions_dir.exists():
        for d_file in decisions_dir.glob("*.md"):
            content = read_file(d_file)
            decisions_md += f"### {d_file.name}\n\n{content}\n\n"
    if not decisions_md:
        decisions_md = "*Рішень не знайдено.*"

    # Собираем QMD структуру
    qmd_content = f"""---
title: "Сводный и финальный отчет: {case_dir.name}"
author: "Электронный Консультант OEE"
date: today
format:
  html:
    theme: litera
    toc: true
    number-sections: true
    code-fold: true
  pdf:
    toc: true
    number-sections: true
    colorlinks: true
execute:
  echo: false
---

# Часть 1. Сводный отчет

## 1. Краткое общее описание предъявленной модели
*(Основано на первичном запросе)*

{raw_input}

## 2. Вопросы, которые необходимо прояснить
*(Пробелы в знаниях (Information Gaps) и онтологических моделях)*

{unknowns_md}

---

# Часть 2. Финальный отчет

## 3. Анализ предъявленной модели и выявленные проблемы
*(Описание выявленных проблем с аргументами, почему это проблемы)*

{problems_md}

## 4. Предлагаемые решения
*(Архитектурные решения и выбор альтернатив)*

{decisions_md}

"""
    # Сохраняем в папку reports
    reports_dir = case_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = reports_dir / output_file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(qmd_content)
        
    print(f"Отчет успешно сохранен в: {output_path}")
    print(f"Для компиляции в HTML/PDF используйте команду Quarto:")
    print(f"  quarto render '{output_path}'")
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Генерация Quarto отчета для кейса")
    parser.add_argument("case_id", help="Идентификатор кейса (например, case_20260301_003)")
    parser.add_argument("--root", default=".", help="Корневая директория проекта")
    parser.add_argument("--out", default="final_report.qmd", help="Имя выходного файла")
    
    args = parser.parse_args()
    
    project_root = Path(args.root).resolve()
    case_dir = project_root / "cases" / args.case_id
    
    if not case_dir.exists():
        print(f"Ошибка: Директория кейса не найдена {case_dir}")
        sys.exit(1)
        
    generate_report(case_dir, Path(args.out))
