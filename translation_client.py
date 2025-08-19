import logging
from google.cloud import translate_v2 as translate
import os

# Make sure to set the GOOGLE_APPLICATION_CREDENTIALS environment variable
# In a local environment, you can do this by running:
# export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/keyfile.json"

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
        # The free tier of Google Translate API (v2) requires 'source_language'
        # We can detect it, but it's more reliable to specify it if known.
        # For this bot, we assume the source is always English.
        result = client.translate(text, target_language=target_language, source_language='en')
        return result['translatedText']
    except Exception as e:
        logging.error(f"Google Translate API call failed for target language '{target_language}': {e}")
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
        return result['language']
    except Exception as e:
        logging.error(f"Google Translate language detection failed: {e}")
        return None
