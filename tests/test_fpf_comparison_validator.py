import tempfile
import unittest
from pathlib import Path

from app.validation.fpf_comparison_validator import (
    validate_comparison_legality,
    validate_selection_workspace,
)


class FPFComparisonValidatorTests(unittest.TestCase):
    def test_hidden_scalarization_is_detected(self):
        issues = validate_comparison_legality(
            parity_text="Overall weighted score decides the winner.",
            selected_text="- sol_01",
            acceptance_spec_text="## assumptions_to_confirm\n- none",
        )
        self.assertTrue(any(issue.code == "HIDDEN_SCALARIZATION" for issue in issues))

    def test_set_returning_selection_is_allowed(self):
        issues = validate_comparison_legality(
            parity_text="comparison frame: explicit parity and tradeoff table",
            selected_text="- sol_01\n- sol_02",
            acceptance_spec_text="## selection_policy\n- parity before ranking",
        )
        self.assertEqual(issues, [])

    def test_invalid_comparator_basis_blocks_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "cases" / "case_20260319_3001"
            (workspace / "solutions").mkdir(parents=True, exist_ok=True)
            (workspace / "problems").mkdir(parents=True, exist_ok=True)
            (workspace / "solutions" / "ParityReport.md").write_text("Single weighted score used.\n", encoding="utf-8")
            (workspace / "solutions" / "SelectedSolutions.md").write_text("- sol_01\n", encoding="utf-8")
            (workspace / "problems" / "ComparisonAcceptanceSpec.md").write_text("No comparator basis.\n", encoding="utf-8")

            issues = validate_selection_workspace(workspace)
            self.assertTrue(any(issue.code == "HIDDEN_SCALARIZATION" for issue in issues))


if __name__ == "__main__":
    unittest.main()
