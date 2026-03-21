import unittest

from app.validation.fpf_characteristic_validator import validate_characteristic_legality


class FPFCharacteristicValidatorTests(unittest.TestCase):
    def test_chr_target_mixed_with_fact_is_detected(self):
        issues = validate_characteristic_legality(
            "- CHR-02-WASTE-ACCUM should be 0 and is currently a confirmed fact."
        )
        self.assertTrue(any(issue.code == "CHR_TARGET_PRESENTED_AS_FACT" for issue in issues))

    def test_target_marked_as_normative_only_is_allowed(self):
        issues = validate_characteristic_legality("- CHR-02-WASTE-ACCUM target: 0 m3/month.")
        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
