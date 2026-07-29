import tempfile
import unittest
from pathlib import Path

import utils.chat_style as chat_style


class ChatStyleTest(unittest.TestCase):
    def test_style_round_trip_and_clamping(self):
        with tempfile.TemporaryDirectory() as folder:
            original = chat_style.SETTINGS_FILE
            try:
                chat_style.SETTINGS_FILE = Path(folder) / "settings.json"
                chat_style.update_chat_setting(123, "style", "ты пещерный человек")
                chat_style.update_chat_setting(123, "chance", "2")
                config = chat_style.get_chat_settings(123)
                self.assertEqual(config["prompt"], "ты пещерный человек")
                self.assertEqual(config["sticker_chance"], 1.0)
            finally:
                chat_style.SETTINGS_FILE = original

    def test_supported_aliases(self):
        self.assertEqual(chat_style.normalize_setting("style", "x"), ("prompt", "x"))
        self.assertEqual(chat_style.normalize_setting("group", "5"), ("reply_every", 5))
        self.assertEqual(chat_style.normalize_setting("mode", "rag"), ("style_mode", "mystyle"))
        with self.assertRaises(ValueError):
            chat_style.normalize_setting("unknown", "x")


if __name__ == "__main__":
    unittest.main()