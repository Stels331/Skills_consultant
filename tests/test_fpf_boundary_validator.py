import unittest

from app.validation.fpf_boundary_validator import validate_boundary_discipline


class FPFBoundaryValidatorTests(unittest.TestCase):
    def test_mixed_boundary_statement_is_detected(self):
        issues = validate_boundary_discipline(
            "- This gate is legally required, must be enforced, and is accepted only with evidence_ref."
        )
        self.assertTrue(any(issue.code == "FPF_BOUNDARY_SOUP" for issue in issues))

    def test_lawful_separation_does_not_trigger_false_positive(self):
        issues = validate_boundary_discipline(
            "## Hard Constraints\n"
            "- admissibility gate: request must include signed scope.\n"
            "## Evidence\n"
            "- evidence_ref: signed scope record.\n"
        )
        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
