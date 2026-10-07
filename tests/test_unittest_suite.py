import unittest
import asyncio
from googletrans import Translator

class TestGoogletransUnittest(unittest.TestCase):

    def setUp(self):
        self.translator = Translator()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        if hasattr(self.translator, "client") and self.translator.client:
            self.loop.run_until_complete(self.translator.client.aclose())
        self.loop.close()

    def test_simple_translation(self):
        """Unittest: Simple translation (English to Spanish)."""
        result = self.loop.run_until_complete(
            self.translator.translate("Hello", dest="es")
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.dest, "es")
        self.assertTrue(hasattr(result, "text"))

    def test_specific_language_pair(self):
        """Unittest: Specific language pair (German to English)."""
        result = self.loop.run_until_complete(
            self.translator.translate("Guten Morgen", src="de", dest="en")
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.dest, "en")
        self.assertTrue(hasattr(result, "text"))

    def test_language_detection(self):
        """Unittest: Language detection for English."""
        detection = self.loop.run_until_complete(
            self.translator.detect("This is a test sentence in English.")
        )
        self.assertIsNotNone(detection)
        self.assertEqual(detection.lang, "en")

    def test_batch_translation(self):
        """Unittest: Batch translation of multiple sentences."""
        items = ["One", "Two", "Three"]
        results = self.loop.run_until_complete(
            self.translator.translate(items, dest="fr")
        )
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 3)

    def test_special_characters(self):
        """Unittest: Handling unicode and special characters."""
        text = "Pythön & Tränslatïon: 100% test!"
        result = self.loop.run_until_complete(
            self.translator.translate(text, dest="es")
        )
        self.assertIsNotNone(result)
        self.assertIn("100%", result.text)

    def test_invalid_language_code(self):
        """Unittest: Invalid destination language code raises ValueError."""
        with self.assertRaises(ValueError):
            self.loop.run_until_complete(
                self.translator.translate("Hello", dest="nonexistent_lang")
            )

if __name__ == "__main__":
    unittest.main()
