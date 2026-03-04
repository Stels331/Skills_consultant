#!/usr/bin/env python3
import json
import sys
from pathlib import Path

# Allow importing app.* from project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.llm.client import generate_markdown_with_skill

def main():
    # Read the JSON payload from stdin
    input_data = sys.stdin.read()
    if not input_data:
        return
        
    try:
        req = json.loads(input_data)
    except json.JSONDecodeError:
        print("Error: Invalid JSON on stdin", file=sys.stderr)
        return

    # Extract prompts/payload and render markdown through the local backend.
    # This keeps contracts stable while requests are routed via antigravity bridge.
    system_prompt = req.get("system_prompt", "")
    user_payload = req.get("user_payload", {})
    try:
        response = generate_markdown_with_skill(
            system_skill_prompt=system_prompt,
            user_payload=user_payload,
            mode="local",
        )
    except Exception as exc:
        print(f"Bridge backend error: {exc}", file=sys.stderr)
        return

    # Print exactly markdown to stdout
    print(response or "")

if __name__ == "__main__":
    main()
