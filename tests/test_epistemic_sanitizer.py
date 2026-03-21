import unittest

from app.pipeline.epistemic_sanitizer import detect_unanchored_claim_lines, soften_unanchored_claims


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


if __name__ == "__main__":
    unittest.main()
