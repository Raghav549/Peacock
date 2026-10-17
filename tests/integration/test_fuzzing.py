import unittest

from peacock.fuzzing import fuzz_artifact, fuzz_lexer, fuzz_model, fuzz_parser, run_all


class FuzzTests(unittest.TestCase):
    def test_lexer_never_crashes(self):
        report = fuzz_lexer(300, seed=11)
        self.assertTrue(report.ok, report.crashes[:3])
        self.assertEqual(report.handled + len(report.crashes), 300)

    def test_parser_never_crashes(self):
        report = fuzz_parser(300, seed=12)
        self.assertTrue(report.ok, report.crashes[:3])

    def test_artifact_never_crashes(self):
        report = fuzz_artifact(300, seed=13)
        self.assertTrue(report.ok, report.crashes[:3])

    def test_model_never_crashes(self):
        report = fuzz_model(200, seed=14)
        self.assertTrue(report.ok, report.crashes[:3])

    def test_reports_are_deterministic(self):
        first = fuzz_lexer(100, seed=7).to_dict()
        second = fuzz_lexer(100, seed=7).to_dict()
        self.assertEqual(first, second)

    def test_run_all_reports_every_target(self):
        reports = run_all(50, seed=1)
        self.assertEqual({r.target for r in reports}, {"lexer", "parser", "artifact", "model"})
        self.assertTrue(all(r.ok for r in reports))


if __name__ == "__main__":
    unittest.main()
