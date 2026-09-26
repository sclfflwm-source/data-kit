import tempfile
import unittest
from pathlib import Path

from data_kit import date_gaps, duplicates, jsonl_count, profile, shape, shape_diff, validate


class DataKitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_csv_profile_and_validation(self):
        path = self.root / "items.csv"
        path.write_text("id,date,amount\na,2026-10-01,1.5\na,2026-10-03,bad\n")
        self.assertEqual(profile(path)["columns"]["id"]["distinct"], 1)
        issues = validate(path, {"required": ["id"], "unique": ["id"],
                                 "types": {"date": "date", "amount": "decimal"}})
        self.assertEqual(len(issues), 2)

    def test_shape_diff_reports_nested_change(self):
        old = shape({"user": {"id": 1}})
        new = shape({"user": {"id": "one", "name": "Ada"}})
        self.assertEqual(len(shape_diff(old, new)), 2)

    def test_duplicate_files_are_grouped(self):
        (self.root / "a.txt").write_text("same")
        (self.root / "b.txt").write_text("same")
        (self.root / "c.txt").write_text("different")
        self.assertEqual(duplicates(self.root), [["a.txt", "b.txt"]])

    def test_jsonl_counter_rejects_missing_field(self):
        path = self.root / "events.jsonl"
        path.write_text('{"level":"error"}\n{"level":"error"}\n')
        self.assertEqual(jsonl_count(path, "level"), {"error": 2})
        path.write_text('{}\n')
        with self.assertRaisesRegex(ValueError, "missing level"):
            jsonl_count(path, "level")

    def test_date_gaps_finds_missing_day(self):
        path = self.root / "days.csv"
        path.write_text("date\n2026-10-01\n2026-10-03\n")
        self.assertEqual(date_gaps(path, "date"), ["2026-10-02"])


if __name__ == "__main__":
    unittest.main()
