import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.pipeline.solution_portfolio import _parse_candidates, run_solution_portfolio
from app.validation.contract_validator import _validate_markdown_contract


class TestSolutionPortfolioParse(unittest.TestCase):
    def test_parse_result_clean_when_all_fields_explicit(self):
        body = """
        ## sol_00_status_quo
        - type: baseline
        - assurance_level: low
        
        ## sol_01_fix1
        - type: process
        - assurance_level: medium
        - intervention_force: weak
        - relevance_basis: rollout_relevant
        
        ## sol_02_fix2
        - type: architecture
        - assurance_level: high
        - intervention_force: medium
        - relevance_basis: pareto_relevant
        
        ## sol_03_fix3
        - type: policy
        - assurance_level: low
        - intervention_force: strong
        - relevance_basis: pareto_relevant
        """
        result = _parse_candidates(body, allow_inference=False)
        self.assertEqual(result.parse_quality, "clean")
        self.assertFalse(result.missing_fields)
        self.assertEqual(result.field_trust["sol_01_fix1"]["intervention_force"].F, "explicit")

    def test_parse_result_normalized_when_alias_used(self):
        body = """
        ## sol_00_status_quo
        - type: baseline
        - assurance_level: low
        
        ## sol_01_fix1
        - type: process
        - уровень уверенности: medium
        - сила вмешательства: слабое
        - relevance basis: rollout_relevant
        
        ## sol_02_fix2
        - type: architecture
        - assurance_level: high
        - intervention_force: medium
        - relevance_basis: pareto_relevant
        
        ## sol_03_fix3
        - type: policy
        - assurance_level: low
        - intervention_force: strong
        - relevance_basis: pareto_relevant
        """
        result = _parse_candidates(body, allow_inference=False)
        self.assertIn(result.parse_quality, ["clean", "normalized"])
        self.assertEqual(result.field_trust["sol_01_fix1"]["intervention_force"].normalization_level, "value_translated")

    def test_parse_result_inferred_when_field_missing(self):
        body = """
        ## sol_00_status_quo
        - type: baseline
        - assurance_level: low
        
        ## sol_01_weak_fix
        - type: process
        - assurance_level: medium
        - relevance_basis: rollout_relevant
        
        ## sol_02_fix2
        - type: architecture
        - assurance_level: high
        - intervention_force: medium
        - relevance_basis: pareto_relevant
        
        ## sol_03_fix3
        - type: policy
        - assurance_level: low
        - intervention_force: strong
        - relevance_basis: pareto_relevant
        """
        result = _parse_candidates(body, allow_inference=True)
        self.assertEqual(result.parse_quality, "inferred")
        self.assertEqual(result.candidates["sol_01_weak_fix"]["intervention_force"], "weak")
        self.assertEqual(result.field_trust["sol_01_weak_fix"]["intervention_force"].normalization_level, "inferred")

    @patch('app.pipeline.solution_portfolio.generate_markdown_with_skill')
    @patch('app.pipeline.solution_portfolio.emit_projection')
    def test_retry_not_called_when_parse_is_clean(self, mock_emit, mock_generate):
        body = """
        ## sol_00_status_quo
        - type: baseline
        - assurance_level: low
        
        ## sol_01_fix1
        - type: process
        - assurance_level: medium
        - intervention_force: weak
        - relevance_basis: rollout_relevant
        
        ## sol_02_fix2
        - type: architecture
        - assurance_level: high
        - intervention_force: medium
        - relevance_basis: pareto_relevant
        
        ## sol_03_fix3
        - type: policy
        - assurance_level: low
        - intervention_force: strong
        - relevance_basis: pareto_relevant
        """
        mock_generate.return_value = body
        mock_emit.return_value = ""

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "cases" / "test_case"
            (workspace / "problems").mkdir(parents=True)
            (workspace / "problems" / "SelectedProblemCard.md").write_text("Test", encoding="utf-8")
            (workspace / "problems" / "ComparisonAcceptanceSpec.md").write_text("Test", encoding="utf-8")

            run_solution_portfolio(Path(tmp), "test_case", "local")

        # Ensure generate was only called once
        self.assertEqual(mock_generate.call_count, 1)

    @patch('app.pipeline.solution_portfolio.generate_markdown_with_skill')
    @patch('app.pipeline.solution_portfolio.emit_projection')
    def test_fallback_only_after_retry_fails(self, mock_emit, mock_generate):
        bad_body = """
        ## sol_00_status_quo
        - type: baseline
        - assurance_level: low
        
        ## sol_01_fix1
        - type: process
        - assurance_level: medium
        
        ## sol_02_fix2
        - type: architecture
        - assurance_level: high
        
        ## sol_03_fix3
        - type: policy
        - assurance_level: low
        """
        # Both first and second try fail
        mock_generate.side_effect = [bad_body, bad_body]
        mock_emit.return_value = ""

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "cases" / "test_case"
            (workspace / "problems").mkdir(parents=True)
            (workspace / "problems" / "SelectedProblemCard.md").write_text("Test", encoding="utf-8")
            (workspace / "problems" / "ComparisonAcceptanceSpec.md").write_text("Test", encoding="utf-8")

            run_solution_portfolio(Path(tmp), "test_case", "local")

        # Ensure generate was called twice (initial + retry)
        self.assertEqual(mock_generate.call_count, 2)


class TestContractValidatorIntegration(unittest.TestCase):
    def test_contract_validator_degrades_on_inferred_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path = Path(tmp) / "SolutionPortfolio.md"
            content = """---
artifact_id: 'test__solution_portfolio'
artifact_type: 'solution_portfolio'
stage: 'solution_factory'
parse_metadata: {"parse_quality": "inferred", "inferred_fields": {"sol_01_fix1": [{"field": "intervention_force", "F": "inferred_text", "R": "low", "source": "text_inference:key=intervention_force:detail=rule=force_keyword_weak"}]}}
---

## sol_00_status_quo
- type: baseline
- assurance_level: low
"""
            artifact_path.write_text(content, encoding="utf-8")
            
            # Using _validate_markdown_contract
            issues = _validate_markdown_contract({"artifact_type": "solution_portfolio"}, artifact_path)
            print("ISSUES:", issues)
            
            degrade_issue = next((i for i in issues if i.code == "SOLUTION_PORTFOLIO_INFERRED_FIELDS"), None)
            self.assertIsNotNone(degrade_issue)
            self.assertEqual(degrade_issue.severity, "warning")
            self.assertEqual(degrade_issue.action, "degrade")

if __name__ == "__main__":
    unittest.main()
