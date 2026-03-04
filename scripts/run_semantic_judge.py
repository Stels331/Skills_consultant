#!/usr/bin/env python3
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.principles.library import load_principles_for_stage
from app.validation.artifact_contract_validator import read_frontmatter_document
from app.validation.semantic_judge import run_semantic_judge


def main() -> int:
    parser = argparse.ArgumentParser(description="Run semantic LLM-as-judge validation")
    parser.add_argument("--stage", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--mode", default="local", choices=["local", "openai", "antigravity"])
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    artifact_path = Path(args.artifact).resolve()

    doc = read_frontmatter_document(artifact_path)
    principles = load_principles_for_stage(project_root, args.stage)
    result = run_semantic_judge(
        stage_name=args.stage,
        artifact_path=artifact_path,
        frontmatter=doc.frontmatter,
        body_text=doc.body,
        principles=principles,
        mode=args.mode,
    )

    print(
        json.dumps(
            {
                "is_valid": result.is_valid,
                "provider": result.provider,
                "score": result.score,
                "recommendation": result.recommendation,
                "issues": [i.__dict__ for i in result.issues],
                "principles_loaded": [p.principle_id for p in principles],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.recommendation != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
