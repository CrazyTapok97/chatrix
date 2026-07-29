import tempfile
import unittest
from pathlib import Path

import utils.native_features as features
from utils.native_features import parse_draw_request, parse_ship_pair, safe_calculate


class NativeFeaturesTest(unittest.TestCase):
    def test_safe_calculate(self):
        self.assertEqual(safe_calculate("2 + 3 * 4"), 14)
        self.assertEqual(safe_calculate("sqrt(81) + 1"), 10)

    def test_safe_calculate_rejects_code(self):
        with self.assertRaises(ValueError):
            safe_calculate("__import__('os').system('id')")

    def test_parse_draw_request(self):
        prompt, width, height, style = parse_draw_request("кот --wide --anime")
        self.assertEqual(prompt, "кот")
        self.assertEqual((width, height), (1344, 768))
        self.assertIn("anime", style)

    def test_migrated_task_format(self):
        with tempfile.TemporaryDirectory() as folder:
            original = features.TASKS_FILE
            try:
                features.TASKS_FILE = Path(folder) / "tasks.json"
                tasks = features.add_task(42, "проверить перенос", -100)
                self.assertEqual(tasks, ["проверить перенос"])
                self.assertEqual(features.load_tasks(42), ["проверить перенос"])
            finally:
                features.TASKS_FILE = original
    def test_parse_ship_pair(self):
        self.assertEqual(parse_ship_pair("Маша и Вася"), ("Маша", "Вася"))
        self.assertEqual(parse_ship_pair("Alice + Bob"), ("Alice", "Bob"))
        with self.assertRaises(ValueError):
            parse_ship_pair("только один")


if __name__ == "__main__":
    unittest.main()