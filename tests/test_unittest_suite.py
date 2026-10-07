import unittest
import asyncio
import time
from googletrans import Translator

class TestGoogletransUnittest(unittest.TestCase):

    def setUp(self):
        self.translator = Translator()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.tested = None
        self.expected = None
        self.returned = None

    def tearDown(self):
        if hasattr(self.translator, "client") and self.translator.client:
            self.loop.run_until_complete(self.translator.client.aclose())
        self.loop.close()

    def _run_translation_check(self, text, src='auto', dest='en'):
        """
        Helper method to run async translate call, checking for HTTP 429
        or English text returned as-is when translating to non-English.
        """
        try:
            if src == 'auto':
                result = self.loop.run_until_complete(
                    self.translator.translate(text, dest=dest)
                )
            else:
                result = self.loop.run_until_complete(
                    self.translator.translate(text, src=src, dest=dest)
                )

            returned_text = result.text if hasattr(result, 'text') else str(result)

            if dest.lower() != 'en' and returned_text.strip() == text.strip():
                # Silently returned as-is
                time.sleep(10)
                self.fail(f"Translation returned text as-is without translating! Input: '{text}', Returned: '{returned_text}'. Rate limit / HTTP 429 suspected.")

            return returned_text, result
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "too many requests" in err_str:
                time.sleep(10)
                self.fail(f"HTTP 429 Rate Limit encountered: {e}")
            raise e

    # --- Easy Tests ---

    def test_pypi_readme_korean_example(self):
        """Unittest (PyPI README Simple Example 1): Korean text translation to English."""
        self.tested = "Translating '안녕하세요.' to English (pypi description standard usage)"
        self.expected = "Non-empty translated text in English (e.g. 'hello' or 'hi')"

        returned_text, result = self._run_translation_check("안녕하세요.", dest="en")
        self.returned = f"'{returned_text}' (src={result.src}, dest={result.dest})"

        self.assertIsNotNone(returned_text)
        self.assertGreaterThan(len(returned_text), 0)

    def test_pypi_readme_latin_example(self):
        """Unittest (PyPI README Simple Example 2): Latin 'veritas lux mea' to English."""
        self.tested = "Translating Latin 'veritas lux mea' to English with explicit src='la'"
        self.expected = "Translated text containing 'truth' or 'light'"

        returned_text, result = self._run_translation_check("veritas lux mea", src="la", dest="en")
        self.returned = f"'{returned_text}' (src={result.src}, dest={result.dest})"

        self.assertIsNotNone(returned_text)
        self.assertTrue("truth" in returned_text.lower() or "light" in returned_text.lower())

    def test_simple_translation(self):
        """Unittest: Simple single-word translation (English to Spanish)."""
        self.tested = "Translating word 'Hello' to Spanish (dest='es')"
        self.expected = "'Hola'"

        returned_text, result = self._run_translation_check("Hello", dest="es")
        self.returned = f"'{returned_text}' (dest={result.dest})"

        self.assertIsNotNone(result)
        self.assertEqual(result.dest, "es")
        self.assertIn(returned_text.lower(), ["hola", "¡hola!"])

    # --- Medium / Language Pair & Detection Tests ---

    def test_specific_language_pair(self):
        """Unittest: Specific language pair (German to English)."""
        self.tested = "Translating German phrase 'Guten Morgen' to English (src='de', dest='en')"
        self.expected = "'Good morning'"

        returned_text, result = self._run_translation_check("Guten Morgen", src="de", dest="en")
        self.returned = f"'{returned_text}' (src={result.src}, dest={result.dest})"

        self.assertIsNotNone(result)
        self.assertEqual(result.dest, "en")
        self.assertIn("good morning", returned_text.lower())

    def test_language_detection(self):
        """Unittest: Language auto-detection for English."""
        self.tested = "Detecting language for: 'This is a test sentence in English.'"
        self.expected = "Detected language code 'en'"

        detection = self.loop.run_until_complete(
            self.translator.detect("This is a test sentence in English.")
        )
        returned_lang = detection.lang if hasattr(detection, "lang") else str(detection)
        self.returned = f"lang='{returned_lang}', confidence={getattr(detection, 'confidence', 'N/A')}"

        self.assertIsNotNone(detection)
        self.assertEqual(returned_lang, "en")

    # --- Complicated & Edge Case Tests ---

    def test_english_to_german_as_is_check(self):
        """Unittest (Complicated): English to German, ensuring text is not returned as-is."""
        src_text = "The quick brown fox jumps over the lazy dog."
        self.tested = f"Translating English sentence '{src_text}' to German (dest='de')"
        self.expected = "German translation distinct from English source text (e.g. 'Der schnelle braune Fuchs...')"

        returned_text, result = self._run_translation_check(src_text, dest="de")
        self.returned = f"'{returned_text}'"

        self.assertNotEqual(returned_text.strip(), src_text.strip())
        self.assertTrue("fuchs" in returned_text.lower() or "schnelle" in returned_text.lower() or "springt" in returned_text.lower())

    def test_batch_translation(self):
        """Unittest (Complicated): Batch translation of multiple sentences to French."""
        items = ["One", "Two", "Three"]
        self.tested = f"Batch translating list: {items} to French (dest='fr')"
        self.expected = "List of 3 Translated objects with dest='fr'"

        results = self.loop.run_until_complete(
            self.translator.translate(items, dest="fr")
        )
        returned_list = [r.text for r in results]

        for orig, trans in zip(items, returned_list):
            if orig == trans:
                time.sleep(10)
                self.fail(f"Batch item '{orig}' returned as-is without translation! Rate limit suspected.")

        self.returned = f"List of 3 items: {returned_list}"
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 3)

    def test_special_characters(self):
        """Unittest (Complicated): Handling unicode, special characters, and numbers."""
        text = "Pythön & Tränslatïon: 100% test!"
        self.tested = f"Translating unicode/special char text '{text}' to Spanish (dest='es')"
        self.expected = "Translated text preserving '100%'"

        returned_text, result = self._run_translation_check(text, dest="es")
        self.returned = f"'{returned_text}'"

        self.assertIsNotNone(result)
        self.assertIn("100%", returned_text)

    def test_multiline_long_text(self):
        """Unittest (Complicated): Multiline long text translation to German."""
        long_text = (
            "Googletrans is a free and unlimited python library that implemented "
            "Google Translate API.\n"
            "It uses the Google Translate Ajax API to make calls to such methods "
            "as detect and translate."
        )
        self.tested = f"Translating multiline text (length {len(long_text)} chars) to German (dest='de')"
        self.expected = "German translated text longer than 20 chars, not identical to English source"

        returned_text, result = self._run_translation_check(long_text, dest="de")
        self.returned = f"'{returned_text[:60]}...' (Length: {len(returned_text)})"

        self.assertGreaterThan(len(returned_text), 20)
        self.assertNotEqual(returned_text, long_text)

    def test_invalid_language_code(self):
        """Unittest (Edge Case): Invalid destination language code raises ValueError."""
        self.tested = "Translating 'Hello' with invalid destination language 'nonexistent_lang'"
        self.expected = "ValueError raised due to invalid language code"

        with self.assertRaises(ValueError) as ctx:
            self.loop.run_until_complete(
                self.translator.translate("Hello", dest="nonexistent_lang")
            )
        self.returned = f"Raised exception: {type(ctx.exception).__name__}: {ctx.exception}"

    def assertGreaterThan(self, a, b):
        self.assertTrue(a > b, f"{a} is not greater than {b}")

if __name__ == "__main__":
    unittest.main()
