import asyncio
import time
import pytest
from googletrans import Translator

async def handle_translation_with_check(translator, text, src='auto', dest='en', expected_check=None):
    """
    Executes translation with rate limit detection and as-is verification.
    If 429 error occurs or if source text is returned completely unchanged when
    translating between different languages, sleep 10s and raise an AssertionError/Exception.
    """
    tested_desc = f"Translating text: '{text}' (src='{src}', dest='{dest}')"
    try:
        if src == 'auto':
            result = await translator.translate(text, dest=dest)
        else:
            result = await translator.translate(text, src=src, dest=dest)

        returned_text = result.text if hasattr(result, 'text') else str(result)

        # Check if returned text is identical to source text when translating across languages
        # (e.g. non-English to English or English to non-English)
        detected_src = getattr(result, 'src', src)
        if (dest.lower() != 'auto' and detected_src.lower() != dest.lower()) and returned_text.strip() == text.strip():
            # Possible rate limit or silent as-is fallback error!
            await asyncio.sleep(10)
            pytest.fail(f"Translation returned text as-is without translating! Input: '{text}', Returned: '{returned_text}'. HTTP 429 or rate limit suspected.")

        return tested_desc, returned_text, result
    except Exception as e:
        err_str = str(e).lower()
        if "429" in err_str or "too many requests" in err_str:
            await asyncio.sleep(10)
            pytest.fail(f"HTTP 429 Rate Limit encountered: {e}")
        raise e

# --- Easy Tests ---
 
@pytest.mark.asyncio
async def test_pypi_readme_korean_example(request):
    """PyPI / GitHub README Simple Example 1: Translate Korean text to English."""
    translator = Translator()
    try:
        tested = "Translating '안녕하세요.' to English (pypi description standard usage)"
        expected = "Non-empty translated text in English (e.g. 'hello' or 'hi')"
        request.node.user_properties.append(("tested", tested))
        request.node.user_properties.append(("expected", expected))

        tested_info, returned_text, result = await handle_translation_with_check(translator, "안녕하세요.", dest="en")
        request.node.user_properties.append(("returned", f"'{returned_text}' (src={result.src}, dest={result.dest})"))

        assert returned_text is not None and len(returned_text) > 0
    finally:
        if hasattr(translator, "client") and translator.client:
            await translator.client.aclose()

@pytest.mark.asyncio
async def test_pypi_readme_latin_example(request):
    """PyPI / GitHub README Simple Example 2: Translate Latin 'veritas lux mea' to English."""
    translator = Translator()
    try:
        tested = "Translating Latin 'veritas lux mea' to English with explicit src='la'"
        expected = "Translated text containing 'truth' or 'light'"
        request.node.user_properties.append(("tested", tested))
        request.node.user_properties.append(("expected", expected))

        tested_info, returned_text, result = await handle_translation_with_check(translator, "veritas lux mea", src="la", dest="en")
        request.node.user_properties.append(("returned", f"'{returned_text}' (src={result.src}, dest={result.dest})"))

        assert returned_text is not None
        assert "truth" in returned_text.lower() or "light" in returned_text.lower()
    finally:
        if hasattr(translator, "client") and translator.client:
            await translator.client.aclose()

@pytest.mark.asyncio
async def test_simple_word_english_to_spanish(request):
    """Easy Test: Single word translation from English to Spanish."""
    translator = Translator()
    try:
        tested = "Translating word 'Hello' to Spanish (dest='es')"
        expected = "'Hola'"
        request.node.user_properties.append(("tested", tested))
        request.node.user_properties.append(("expected", expected))

        tested_info, returned_text, result = await handle_translation_with_check(translator, "Hello", dest="es")
        request.node.user_properties.append(("returned", f"'{returned_text}' (dest={result.dest})"))

        assert result.dest == "es"
        assert returned_text.lower() in ["hola", "¡hola!"]
    finally:
        if hasattr(translator, "client") and translator.client:
            await translator.client.aclose()

# --- Medium / Language Pair & Detection Tests ---

@pytest.mark.asyncio
async def test_specific_language_pair_german_to_english(request):
    """Medium Test: German to English translation."""
    translator = Translator()
    try:
        tested = "Translating German phrase 'Guten Morgen' to English (src='de', dest='en')"
        expected = "'Good morning'"
        request.node.user_properties.append(("tested", tested))
        request.node.user_properties.append(("expected", expected))

        tested_info, returned_text, result = await handle_translation_with_check(translator, "Guten Morgen", src="de", dest="en")
        request.node.user_properties.append(("returned", f"'{returned_text}' (src={result.src}, dest={result.dest})"))

        assert result.dest == "en"
        assert "good morning" in returned_text.lower()
    finally:
        if hasattr(translator, "client") and translator.client:
            await translator.client.aclose()

@pytest.mark.asyncio
async def test_language_detection(request):
    """Medium Test: Auto-detect language for English sentence."""
    translator = Translator()
    try:
        tested = "Detecting language for: 'This is a test sentence in English.'"
        expected = "Detected language code 'en'"
        request.node.user_properties.append(("tested", tested))
        request.node.user_properties.append(("expected", expected))

        detection = await translator.detect("This is a test sentence in English.")
        returned_lang = detection.lang if hasattr(detection, "lang") else str(detection)
        request.node.user_properties.append(("returned", f"lang='{returned_lang}', confidence={getattr(detection, 'confidence', 'N/A')}"))

        assert detection is not None
        assert returned_lang == "en"
    finally:
        if hasattr(translator, "client") and translator.client:
            await translator.client.aclose()

# --- Complicated & Edge Case Tests ---

@pytest.mark.asyncio
async def test_english_to_german_as_is_check(request):
    """Complicated Test: English sentence to German, checking text is NOT returned as-is."""
    translator = Translator()
    try:
        src_text = "The quick brown fox jumps over the lazy dog."
        tested = f"Translating English sentence '{src_text}' to German (dest='de')"
        expected = "German translation distinct from English source text (e.g. 'Der schnelle braune Fuchs...')"
        request.node.user_properties.append(("tested", tested))
        request.node.user_properties.append(("expected", expected))

        tested_info, returned_text, result = await handle_translation_with_check(translator, src_text, dest="de")
        request.node.user_properties.append(("returned", f"'{returned_text}'"))

        assert returned_text.strip() != src_text.strip()
        assert "fuchs" in returned_text.lower() or "schnelle" in returned_text.lower() or "springt" in returned_text.lower()
    finally:
        if hasattr(translator, "client") and translator.client:
            await translator.client.aclose()

@pytest.mark.asyncio
async def test_batch_translation(request):
    """Complicated Test: Batch list of strings translation to Japanese."""
    translator = Translator()
    try:
        texts = ["Good morning", "Thank you", "Goodbye"]
        tested = f"Batch translating list: {texts} to Japanese (dest='ja')"
        expected = "List of 3 Translated objects with dest='ja'"
        request.node.user_properties.append(("tested", tested))
        request.node.user_properties.append(("expected", expected))

        results = await translator.translate(texts, dest="ja")
        returned_list = [r.text for r in results]

        # Check as-is on batch
        for orig, trans in zip(texts, returned_list):
            if orig == trans:
                await asyncio.sleep(10)
                pytest.fail(f"Batch item '{orig}' returned as-is without translation! Rate limit suspected.")

        request.node.user_properties.append(("returned", f"List of 3 items: {returned_list}"))

        assert isinstance(results, list)
        assert len(results) == 3
        assert all(r.dest == "ja" for r in results)
    finally:
        if hasattr(translator, "client") and translator.client:
            await translator.client.aclose()

@pytest.mark.asyncio
async def test_special_characters_and_formatting(request):
    """Complicated Test: Special characters, numbers, HTML tags preservation."""
    translator = Translator()
    try:
        text = "Hello <b>world</b>! Special symbols: @#$% & 1234."
        tested = f"Translating formatted HTML text '{text}' to Spanish (dest='es')"
        expected = "Translated text preserving HTML tags <b>...</b>, symbols @#$%, and numbers 1234"
        request.node.user_properties.append(("tested", tested))
        request.node.user_properties.append(("expected", expected))

        tested_info, returned_text, result = await handle_translation_with_check(translator, text, dest="es")
        request.node.user_properties.append(("returned", f"'{returned_text}'"))

        assert "1234" in returned_text
        assert "<b>" in returned_text or "world" in returned_text.lower() or "mundo" in returned_text.lower()
    finally:
        if hasattr(translator, "client") and translator.client:
            await translator.client.aclose()

@pytest.mark.asyncio
async def test_multiline_long_text(request):
    """Complicated Test: Multiline long text translation to German."""
    translator = Translator()
    try:
        long_text = (
            "Googletrans is a free and unlimited python library that implemented "
            "Google Translate API.\n"
            "It uses the Google Translate Ajax API to make calls to such methods "
            "as detect and translate."
        )
        tested = f"Translating multiline text (length {len(long_text)} chars) to German (dest='de')"
        expected = "German translated text longer than 20 chars, not identical to English source"
        request.node.user_properties.append(("tested", tested))
        request.node.user_properties.append(("expected", expected))

        tested_info, returned_text, result = await handle_translation_with_check(translator, long_text, dest="de")
        request.node.user_properties.append(("returned", f"'{returned_text[:60]}...' (Length: {len(returned_text)})"))

        assert len(returned_text) > 20
        assert returned_text != long_text
    finally:
        if hasattr(translator, "client") and translator.client:
            await translator.client.aclose()

@pytest.mark.asyncio
async def test_invalid_language_code(request):
    """Edge Case Test: Invalid language code raises ValueError."""
    translator = Translator()
    try:
        tested = "Translating 'Hello' with invalid destination language 'invalid_lang_12345'"
        expected = "ValueError raised due to invalid language code"
        request.node.user_properties.append(("tested", tested))
        request.node.user_properties.append(("expected", expected))

        with pytest.raises(ValueError) as exc_info:
            await translator.translate("Hello", dest="invalid_lang_12345")

        returned_str = f"Raised exception: {exc_info.type.__name__}: {exc_info.value}"
        request.node.user_properties.append(("returned", returned_str))
    finally:
        if hasattr(translator, "client") and translator.client:
            await translator.client.aclose()
