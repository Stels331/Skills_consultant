import unittest
import tempfile
from pathlib import Path

from app.pipeline.epistemic_sanitizer import (
    detect_unanchored_claim_lines,
    enforce_goldilocks_signals,
    harden_generated_artifact,
    normalize_domain_language,
    soften_unanchored_claims,
)


class EpistemicSanitizerTests(unittest.TestCase):
    def test_softens_hard_numeric_claims(self):
        body = "Бункеры переполнятся за 3-5 дней. Банкротство через несколько недель."
        out = soften_unanchored_claims(body)
        self.assertIn("Гипотеза/оценка:", out)

    def test_keeps_marked_hypothesis_as_is(self):
        body = "Гипотеза: бункеры могут переполниться за 3-5 дней."
        out = soften_unanchored_claims(body)
        self.assertEqual(body, out)

    def test_detects_only_unanchored_numeric_lines(self):
        body = "\n".join(
            [
                "- Гипотеза: риск брака 15%.",
                "- Потери составят 40% при текущем режиме.",
                "- source: measured throughput 20 м³/дн",
            ]
        )
        findings = detect_unanchored_claim_lines(body)
        self.assertEqual(findings, ["- Потери составят 40% при текущем режиме."])

    def test_softens_kwh_and_quarter_claims(self):
        body = "Система рассчитана на 700 кВт/ч и банкротство наступит через 1-2 квартала."
        out = soften_unanchored_claims(body)
        self.assertIn("Гипотеза/оценка:", out)

    def test_enforces_goldilocks_signals_for_problem_artifacts(self):
        body = "\n".join(
            [
                "## facts",
                "- Производство теряет ликвидность.",
                "",
                "## chr_targets",
                "- Маржа должна быть положительной.",
                "",
                "## derived_thresholds",
                "- Cash runway минимум 3 месяца.",
                "",
                "## anti_goodhart_conditions",
                "- Не считать фиктивные сделки.",
                "",
                "## hypotheses_to_validate",
                "- Клиент согласится платить премию.",
            ]
        )
        out = enforce_goldilocks_signals(body)
        self.assertIn("Симптом:", out)
        self.assertIn("Constraint/ограничение:", out)
        self.assertIn("Acceptance/критерий приемки:", out)

    def test_normalizes_service_ops_vocabulary_when_domain_disallowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "analysis").mkdir(parents=True, exist_ok=True)
            (workspace / "analysis" / "domain_profile.json").write_text(
                """
{
  "allowed_ontological_domains": ["industrial_transformation", "governance_crisis"],
  "domain_axes": [{"axis": "industrial_transformation"}]
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            text = "Высокая latency управленческих решений и board decision latency убивают проект."
            out = normalize_domain_language(text, workspace)
        self.assertNotIn("latency", out.lower())
        self.assertIn("задержка управленческих решений", out.lower())

    def test_hardening_pass_combines_domain_and_epistemic_repairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "analysis").mkdir(parents=True, exist_ok=True)
            (workspace / "analysis" / "domain_profile.json").write_text(
                """
{
  "allowed_ontological_domains": ["industrial_transformation"],
  "domain_axes": [{"axis": "industrial_transformation"}]
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            raw = "Board Decision Latency ведет к банкротству через 1-2 квартала."
            out = harden_generated_artifact(raw, stage_name="reporting", workspace_path=workspace)
        self.assertIn("Гипотеза/оценка:", out)
        self.assertNotIn("latency", out.lower())


if __name__ == "__main__":
    unittest.main()
