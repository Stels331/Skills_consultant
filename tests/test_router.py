import json
import tempfile
import unittest
from pathlib import Path

from app.router.phase_controller import PhaseController
from app.state.workspace_manager import WorkspaceManager


class RouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

        # copy schemas from project so guards can validate
        src_schemas = Path(__file__).resolve().parents[1] / "schemas"
        dst_schemas = self.root / "schemas"
        dst_schemas.mkdir(parents=True, exist_ok=True)
        for p in src_schemas.glob("*.schema.json"):
            (dst_schemas / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

        self.manager = WorkspaceManager(self.root)
        self.ref = self.manager.create_workspace("case_20260228_001")
        self.router = PhaseController(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _phase(self) -> str:
        session = json.loads((self.ref.path / "state" / "session_state.json").read_text(encoding="utf-8"))
        return session["current_phase"]

    def _step(self, next_phase: str, evidence_ready: bool = True):
        return self.router.transition(
            self.ref.workspace_id,
            next_phase=next_phase,
            signals={"evidence_ready": evidence_ready},
            required_tokens=1000,
        )

    def test_valid_transition(self):
        result = self._step("PARSING")
        self.assertEqual(result.from_phase, "INTAKE")
        self.assertEqual(result.to_phase, "PARSING")
        self.assertEqual(self._phase(), "PARSING")

    def test_invalid_transition_rejected(self):
        with self.assertRaises(ValueError):
            self._step("MODELING")

    def test_evidence_gate_blocks_solution_factory(self):
        self._step("PARSING")
        self._step("EXTRACTION")
        self._step("TYPIZATION")
        self._step("CHARACTERIZATION")
        self._step("MODELING")
        self._step("EPISTEMIC_ANALYSIS")

        with self.assertRaises(ValueError):
            self.router.transition(
                self.ref.workspace_id,
                next_phase="SOLUTION_FACTORY",
                signals={"evidence_ready": False, "problem_defined": True},
                required_tokens=500,
            )

    def test_context_budget_enforced(self):
        result = self._step("PARSING")
        self.assertFalse(result.compression_required)

        result2 = self.router.transition(
            self.ref.workspace_id,
            next_phase="EXTRACTION",
            signals={"evidence_ready": True},
            required_tokens=35000,
        )
        self.assertTrue(result2.compression_required)
        self.assertEqual(result2.effective_tokens, 3500)

    def test_schema_guard_blocks_transition(self):
        self._step("PARSING")
        self._step("EXTRACTION")
        self._step("TYPIZATION")
        self._step("CHARACTERIZATION")
        self._step("MODELING")

        qpath = self.ref.path / "quality" / "quality_metrics.json"
        bad = json.loads(qpath.read_text(encoding="utf-8"))
        bad["metrics"]["coherence"] = "bad"
        qpath.write_text(json.dumps(bad, ensure_ascii=False, indent=2), encoding="utf-8")

        with self.assertRaises(ValueError):
            self._step("EPISTEMIC_ANALYSIS")


if __name__ == "__main__":
    unittest.main()
