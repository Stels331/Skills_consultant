#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# Подключаем корень проекта
root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))

from app.pipeline.intake_parser import run_intake_parser
from app.pipeline.layer_builder import build_layers
from app.pipeline.viewpoint_runner import run_viewpoints
from app.pipeline.characterization import run_characterization
from app.pipeline.problem_factory import run_problem_factory
from app.pipeline.solution_factory import run_solution_factory
from app.pipeline.reporting import run_reporting
from app.router.orchestrator import StageOrchestrator
from app.state.workspace_manager import WorkspaceManager

def read_document(file_path: Path) -> str:
    """Универсальная читалка файлов, включая .docx через textutil"""
    if not file_path.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path}")
    
    ext = file_path.suffix.lower()
    
    if ext in [".txt", ".md", ".json"]:
        return file_path.read_text(encoding="utf-8")
        
    elif ext in [".docx", ".doc", ".rtf"]:
        print(f"Конвертация документа {ext} в текст...")
        # Используем встроенную утилиту MacOS 'textutil' для извлечения текста
        proc = subprocess.run(
            ["textutil", "-convert", "txt", "-stdout", str(file_path)],
            capture_output=True,
            text=True
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Ошибка при чтении {ext}: {proc.stderr}")
        return proc.stdout
        
    else:
        print(f"Внимание: Неизвестное расширение {ext}, пробуем прочесть как обычный текст...")
        return file_path.read_text(encoding="utf-8", errors="ignore")

def main():
    if len(sys.argv) < 2:
        print("Использование: python3 run_case.py /путь/к/файлу/кейса.docx")
        return 1

    case_file = Path(sys.argv[1]).resolve()
    
    # Считываем текст из файла
    try:
        input_text = read_document(case_file)
    except Exception as e:
        print(f"Ошибка: {e}")
        return 1
        
    if not input_text.strip():
        print("Ошибка: Документ пуст.")
        return 1

    # Загружаем настройки AI
    llm_mode = os.environ.get("LLM_MODE", "antigravity").strip().lower() or "antigravity"
    semantic_mode = os.environ.get("SEMANTIC_JUDGE_MODE", "local").strip().lower() or "local"
    os.environ["LLM_MODE"] = llm_mode
    os.environ["SEMANTIC_JUDGE_MODE"] = semantic_mode
    
    # Создаем новый воркспейс
    manager = WorkspaceManager(root)
    today_str = datetime.now().strftime("%Y%m%d")
    workspace_id = manager.generate_workspace_id(today_str)
    ref = manager.create_workspace(workspace_id)
    
    print(f"==========================================")
    print(f"📂 Запуск разбора: {case_file.name}")
    print(f"📁 Воркспейс: {workspace_id}")
    print(f"🧠 LLM Режим: {llm_mode}")
    print(f"==========================================\n")
    
    # Сохраняем "сырой" файл в папке кейса
    safe_name = case_file.stem + "_input.md"
    (ref.path / "raw" / safe_name).write_text(input_text, encoding="utf-8")
    
    # ------------------------------------
    # ЗАПУСК ЦЕПОЧКИ (CHAIN)
    # ------------------------------------
    print(f"[1/7] Парсинг фактов (Intake)...")
    run_intake_parser(root, workspace_id)
    
    print(f"[2/7] Построение бизнес-слоев (Layers)...")
    build_layers(root, workspace_id, llm_mode=llm_mode)
    
    print(f"[3/7] Анализ стейкхолдеров (Viewpoints)...")
    run_viewpoints(root, workspace_id, llm_mode=llm_mode)
    
    print(f"[4/7] Характеризация бизнеса (Characterization)...")
    run_characterization(root, workspace_id, llm_mode=llm_mode)
    
    print(f"[5/7] Поиск корневой проблемы (Problem Factory)...")
    run_problem_factory(root, workspace_id, llm_mode=llm_mode)
    
    print(f"[6/7] Подбор стратегий решений (Solution Factory)...")
    run_solution_factory(root, workspace_id, llm_mode=llm_mode)
    
    print(f"[7/7] Написание итоговых отчетов с выводом (Reporting)...")
    run_reporting(root, workspace_id, llm_mode=llm_mode)
    
    print("\nПроверка качества на гейтах Оркестратора...")
    orch = StageOrchestrator(root)
    for stage in ["intake", "layers", "viewpoints", "characterization", "problem_factory", "solution_factory", "reporting"]:
        res = orch.run_stage(workspace_id, stage, signals={"allow_reuse": True}, rationale="auto_run")
        status = "✅ PASS" if res.gate_result == "pass" else f"❌ {res.gate_result.upper()}"
        print(f" - [{stage.upper()}]: {status}")

    print(f"\n==========================================")
    print(f"🎉 Готово! Отчеты Консультанта лежат здесь:")
    print(f"📂 {ref.path}/reports/")
    print(f"==========================================")
    return 0

if __name__ == "__main__":
    sys.exit(main())
