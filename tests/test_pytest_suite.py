import pytest
import asyncio
from googletrans import Translator

@pytest.mark.asyncio
async def test_simple_translation():
    """Simple single-word/phrase translation test (English to Spanish)."""
    translator = Translator()
    try:
        result = await translator.translate("Hello", dest="es")
        assert result is not None
        assert result.dest == "es"
        assert hasattr(result, "text")
    finally:
        if hasattr(translator, "client") and translator.client:
            await translator.client.aclose()

@pytest.mark.asyncio
async def test_specific_language_pair():
    """Specific language pair translation (German to English)."""
    translator = Translator()
    try:
        result = await translator.translate("Guten Morgen", src="de", dest="en")
        assert result is not None
        assert result.dest == "en"
        assert hasattr(result, "text")
    finally:
        if hasattr(translator, "client") and translator.client:
            await translator.client.aclose()

@pytest.mark.asyncio
async def test_language_detection():
    """Language auto-detection test."""
    translator = Translator()
    try:
        detection = await translator.detect("This is a test sentence in English.")
        assert detection is not None
        assert detection.lang == "en"
    finally:
        if hasattr(translator, "client") and translator.client:
            await translator.client.aclose()

@pytest.mark.asyncio
async def test_batch_translation():
    """Batch list of strings translation test."""
    translator = Translator()
    try:
        texts = ["Good morning", "Thank you", "Goodbye"]
        results = await translator.translate(texts, dest="ja")
        assert isinstance(results, list)
        assert len(results) == 3
        assert all(r.dest == "ja" for r in results)
    finally:
        if hasattr(translator, "client") and translator.client:
            await translator.client.aclose()

@pytest.mark.asyncio
async def test_special_characters_and_formatting():
    """Complex translation: Special characters, numbers, and HTML tags."""
    translator = Translator()
    try:
        text = "Hello <b>world</b>! Special symbols: @#$% & 1234."
        result = await translator.translate(text, dest="es")
        assert result is not None
        assert "1234" in result.text
        assert "@#$%" in result.text or "@" in result.text
    finally:
        if hasattr(translator, "client") and translator.client:
            await translator.client.aclose()

@pytest.mark.asyncio
async def test_multiline_long_text():
    """Complex translation: Multiline long text."""
    translator = Translator()
    try:
        long_text = (
            "Googletrans is a free and unlimited python library that implemented "
            "Google Translate API.\n"
            "It uses the Google Translate Ajax API to make calls to such methods "
            "as detect and translate."
        )
        result = await translator.translate(long_text, dest="de")
        assert result is not None
        assert len(result.text) > 20
    finally:
        if hasattr(translator, "client") and translator.client:
            await translator.client.aclose()

@pytest.mark.asyncio
async def test_invalid_language_code():
    """Edge case: Invalid language code should raise ValueError."""
    translator = Translator()
    try:
        with pytest.raises(ValueError):
            await translator.translate("Hello", dest="invalid_lang_12345")
    finally:
        if hasattr(translator, "client") and translator.client:
            await translator.client.aclose()
