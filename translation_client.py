import logging
from google.cloud import translate_v2 as translate
import os

def get_google_translate_client():
    """Initializes and returns a Google Translate client."""
    try:
        # The client will automatically find the credentials from the environment variable.
        return translate.Client()
    except Exception as e:
        logging.error(f"Failed to initialize Google Translate client: {e}")
        return None

async def translate_text(text: str, target_language: str, client) -> str | None:
    """
    Translates text to the target language using the Google Translate API.

    Args:
        text: The text to translate.
        target_language: The ISO 639-1 code of the language to translate to.
        client: The Google Translate client instance.

    Returns:
        The translated text, or None if an error occurs.
    """
    if not client or not text:
        return text # Return original text if client is not available or text is empty

    try:
        # Assuming the source is always English for this bot
        result = client.translate(text, target_language=target_language, source_language='en')
        translated_text = result.get('translatedText')

        if translated_text:
            logging.info(f"Successfully translated '{text}' to '{translated_text}' ({target_language})")
            return translated_text
        else:
            logging.warning(f"Google Translate API returned empty result for text: '{text}' and language: '{target_language}'")
            return None

    except Exception as e:
        logging.error(f"Google Translate API call failed for text '{text}' and target language '{target_language}': {e}")
        return None

async def detect_language(text: str, client) -> str | None:
    """
    Detects the language of a given text.

    Args:
        text: The text to analyze.
        client: The Google Translate client instance.

    Returns:
        The detected language code (e.g., 'en', 'es'), or None on error.
    """
    if not client or not text:
        return None

    try:
        result = client.detect_language(text)
        detected_lang = result.get('language')
        if detected_lang:
            return detected_lang
        else:
            logging.warning(f"Google Translate language detection returned empty result for text: '{text}'")
            return None
    except Exception as e:
        logging.error(f"Google Translate language detection failed for text '{text}': {e}")
        return None
