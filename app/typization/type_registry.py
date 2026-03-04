from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


class TypeRegistry:
    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.type_root = self.project_root / "Type"

    def _read(self, name: str) -> Dict[str, Any]:
        path = self.type_root / name
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, name: str, payload: Dict[str, Any]) -> None:
        path = self.type_root / name
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        tmp.replace(path)

    def known_types(self) -> List[Dict[str, Any]]:
        return self._read("known_types.json").get("types", [])

    def candidate_types(self) -> List[Dict[str, Any]]:
        return self._read("candidate_types.json").get("candidates", [])

    def add_candidate_type(self, candidate: Dict[str, Any]) -> None:
        payload = self._read("candidate_types.json")
        existing = payload.setdefault("candidates", [])
        if any(c.get("candidate_id") == candidate.get("candidate_id") for c in existing):
            return
        existing.append(candidate)
        self._write("candidate_types.json", payload)

    def add_mapping(self, mapping: Dict[str, Any]) -> None:
        payload = self._read("mapped_types.json")
        mappings = payload.setdefault("mappings", [])
        mappings.append(mapping)
        self._write("mapped_types.json", payload)
