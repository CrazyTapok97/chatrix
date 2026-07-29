import unittest

from utils.ai_config import build_model_chain, clean_model_response, detect_provider


class AIConfigTest(unittest.TestCase):
    def test_configured_chain_is_deterministic(self):
        config = {
            "primary_model": "openai/gpt-oss-120b",
            "primary_provider": "groq",
            "fallback_model": "qwen/qwen3-32b",
            "fallback_provider": "groq",
            "fallback2_model": "llama-3.3-70b-versatile",
            "fallback2_provider": "groq",
            "final_model": "openrouter/free",
            "final_provider": "openrouter",
        }
        self.assertEqual(build_model_chain(config), [
            ("groq", "openai/gpt-oss-120b"),
            ("groq", "qwen/qwen3-32b"),
            ("groq", "llama-3.3-70b-versatile"),
            ("openrouter", "openrouter/free"),
        ])

    def test_provider_detection_uses_model_catalog(self):
        cache = {"groq": ["qwen/qwen3-32b"], "openrouter": ["openrouter/free"]}
        self.assertEqual(detect_provider("qwen/qwen3-32b", cache), "groq")
        self.assertEqual(detect_provider("openrouter/free", cache), "openrouter")
        self.assertEqual(detect_provider("gemini-3.1-flash-lite", cache), "google")
    def test_reasoning_tags_are_not_sent_to_user(self):
        self.assertEqual(clean_model_response("<think>internal</think>Готово"), "Готово")
        self.assertEqual(clean_model_response("<think>unfinished"), "")
    def test_chain_filters_empty_duplicates_and_non_text_models(self):
        config = {
            "primary_model": "qwen/qwen3-32b", "primary_provider": "groq",
            "fallback_model": "qwen/qwen3-32b", "fallback_provider": "groq",
            "fallback2_model": "google/lyria-3-clip-preview", "fallback2_provider": "openrouter",
            "fallback3_model": "", "fallback3_provider": "groq",
        }
        self.assertEqual(build_model_chain(config), [("groq", "qwen/qwen3-32b")])


if __name__ == "__main__":
    unittest.main()