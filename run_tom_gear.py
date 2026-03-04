import os
import sys
from pathlib import Path

# Add project root to path
root = Path("/Users/stas/Documents/Системное Мышление/Системное мышление/Skills/FPF-skill_2/electronic_consultant_Progect/electronic_consultant_v3")
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

def main():
    llm_mode = os.environ.get("LLM_MODE", "antigravity").strip().lower() or "antigravity"
    semantic_mode = os.environ.get("SEMANTIC_JUDGE_MODE", "local").strip().lower() or "local"
    os.environ["LLM_MODE"] = llm_mode
    os.environ["SEMANTIC_JUDGE_MODE"] = semantic_mode
    
    manager = WorkspaceManager(root)
    workspace_id = manager.generate_workspace_id("20260303")
    ref = manager.create_workspace(workspace_id)
    print(f"Created workspace: {workspace_id}")
    
    # Read docx text
    input_text = """Проект  «TOM GEAR»
Початок 22.02.2024 року
КОРОТКО про ідею 
Лісопереробний комплекс повного циклу переробки деревини, який працює на електроенергії отриманій при  перетворюванні власних відходів (тріска) в газогенераційному реакторі на газ для електрогенераторів. Отриману електроенергію і теплову енергію використовує комплекс в процесі виробництва продуктів із деревини і не тільки.
ОСНОВНІ ЧАСТИНИ
        •       ГАЗОГЕНЕРАЦІЙНА УСТАНОВКА Відео для розуміння, що це таке.
https://youtu.be/wko9N1qH910?si=LcopNI1Q-Zrirr-s
https://youtu.be/Hbrb2RPSrPQ?si=UWFfScV1aQleoXBf
        •       Вузол управління електрогенерації та її безпечного розподілу.
        •       Для забезпечення генерації 700 кВт електроенергії в годину, розрахована потрібна кількість відходів, тобто кількість деревини на вході  від 1500 м куб в місяць..
        •       Лісопильний комплекс робочою потужністю 1500 м куб кругляка в місяць (22-24 робочих зміни).
        •       Розподіленний на 3 участки:
        •       Лісопильний 1500 м куб в місяць ( 22-24 робочих зміни).
        •       Прес вакуумна сушка деревини, термодеревина, імпрегнація деревини до 1000 м куб в місяць ( 30 календарних дні).
        •       Чистий погонаж ( вагонка, чиста заготовка, планкінг, дошка підлоги, терасна дошка тощо)
До 500 м куб в місяць ( 22-24 робочих зміни)
ДОДАТКОВІ ОПЦІЇ
 Можливість виробництва іншої продукції з сухої і вологої деревини шляхом малої механізації процесу виробництва конкретної продукціі. (піддони прості, склеєний погонаж, тощо)
  ЗАПЛАНОВАНІ СТАДІЇ РЕАЛІЗАЦІЇ
        •       Надання ідеї форму стратегічного плану (відмовились від бізнес-плану, для виявлення сірих зон реалізації).
        •       Проект від руки.
        •       Вибір площадки для розміщення.
        •       Підбір обладнання.
        •       Закупка обладнання.
        •       Доставка та монтаж обладнання.
        •       Сировина.
        •       Тестовий запуск кожного участка окремо без газогенерації.
        •       Тестовий запуск газогенраційного реактора.
        •       Тестовий запуск вузла управління розподілу та електрогенерації.
        •       Тестовий всіх участків в гібридному форматі використання електроенергії.
        •       Синхронізація лісопильного комплекса в цілому.
        •       Робота над продуктивністю.
        •       Робота з якістю.
        •       Оптимізація виробничих процесів.
        •       Оптимізація відходів і % виходу готової продукції.
        •       Стабілізація виробництва.
        •       Контрольований контроль якості та продуктивністі.
        •       Вихід на точку беззбитковості. 
        •       Масштабування та розвиток.
ФАКТИЧНО СЬОГОДНІ
        Відмова від реалізації газогенерації. Перенос на пізніше, як наслідок втрата ціннісної пропозиції на виході.
        Проект знаходиться на 8 стадії.  25.12.2025 тестовий запуск частини 1 участка.
ФАКТИЧНА СИТУАЦІЯ НА СЬОГОДНІ 
        •       Порушення внутрішньої комунікації (втома, фінансова не стабільність, хто винен, тощо)
        •       Не спрацювала зовнішня інвестиційна стратегія (залучення зовнішнього інвестора)
        •       Втрата довіри і віри в команду реалізації ( як завжди )
        •       Внутрішня конкуренція за останнє слово між членами правлінням компанією (проектом)
        •       Питання вартості сировини, на сьогодні. Ринок сировини в процесі трансформації і перерозподілу. Труднощі з придбанням якісної сировино по адекватним цінам.
        •       Питання трудових ресурсів, і їхньої кваліфікації.
        •       Виконання домовленостей не в пріоритеті"""

    (ref.path / "raw" / "case_input.md").write_text(input_text, encoding="utf-8")
    
    print("Running intake...")
    run_intake_parser(root, workspace_id)
    print(f"Building layers... (mode={llm_mode})")
    build_layers(root, workspace_id, llm_mode=llm_mode)
    print(f"Running viewpoints... (mode={llm_mode})")
    run_viewpoints(root, workspace_id, llm_mode=llm_mode)
    print(f"Running characterization... (mode={llm_mode})")
    run_characterization(root, workspace_id, llm_mode=llm_mode)
    print(f"Running problem factory... (mode={llm_mode})")
    run_problem_factory(root, workspace_id, llm_mode=llm_mode)
    print(f"Running solution factory... (mode={llm_mode})")
    run_solution_factory(root, workspace_id, llm_mode=llm_mode)
    print(f"Running reporting... (mode={llm_mode})")
    run_reporting(root, workspace_id, llm_mode=llm_mode)
    
    print("Running orchestrator gates...")
    orch = StageOrchestrator(root)
    for stage in ["intake", "layers", "viewpoints", "characterization", "problem_factory", "solution_factory", "reporting"]:
        res = orch.run_stage(workspace_id, stage, signals={"allow_reuse": True}, rationale="tom_gear_analysis")
        print(f"[{stage}] Gate result: {res.gate_result}")
        if res.gate_result == "block":
            print(f"!!! GATE BLOCKED AT {stage} !!!")

    print(f"Done. Reports are in {ref.path}/reports")
    return 0

if __name__ == "__main__":
    sys.exit(main())
