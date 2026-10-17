import json
import unittest

from peacock.benchmarks import format_report, run_benchmarks


class BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_benchmarks(quick=True)

    def test_environment_is_recorded(self):
        self.assertIn("python", self.report.environment)
        self.assertIn("platform", self.report.environment)
        self.assertIn("cpu_count", self.report.environment)
        self.assertIn("total_ram_bytes", self.report.environment)

    def test_expected_categories(self):
        categories = {result.category for result in self.report.results}
        self.assertTrue({"compiler", "runtime", "intelligence", "frontend", "motion"} <= categories)

    def test_measurements_are_positive(self):
        for result in self.report.results:
            self.assertGreater(result.value, 0.0, result.name)
            self.assertTrue(result.unit)

    def test_report_is_serialisable(self):
        payload = self.report.to_dict()
        restored = json.loads(json.dumps(payload))
        self.assertEqual(restored["schema"], 1)
        self.assertEqual(len(restored["results"]), len(self.report.results))

    def test_text_formatting(self):
        text = format_report(self.report)
        self.assertIn("reference bootstrap engine", text)
        self.assertIn("compile_hello", text)
        self.assertIn("note:", text)

    def test_no_comparative_claims(self):
        for note in self.report.notes:
            self.assertNotIn("faster than", note.lower())
            self.assertNotIn("slower than", note.lower())


if __name__ == "__main__":
    unittest.main()
