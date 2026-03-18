import unittest

from app.pipeline.epistemic_sanitizer import soften_unanchored_claims


class EpistemicSanitizerTests(unittest.TestCase):
    def test_softens_hard_numeric_claims(self):
        body = "Бункеры переполнятся за 3-5 дней. Банкротство через несколько недель."
        out = soften_unanchored_claims(body)
        self.assertIn("Гипотеза/оценка:", out)

    def test_keeps_marked_hypothesis_as_is(self):
        body = "Гипотеза: бункеры могут переполниться за 3-5 дней."
        out = soften_unanchored_claims(body)
        self.assertEqual(body, out)


if __name__ == "__main__":
    unittest.main()
