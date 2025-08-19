import json
import logging
import os

CACHE_FILE = "translation_cache.json"
_translation_cache = {}

# --- Cache Management Functions ---

def load_cache():
    """Loads the translation cache from the JSON file into memory."""
    global _translation_cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                _translation_cache = json.load(f)
            logging.info(f"Translation cache loaded from {CACHE_FILE}.")
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Error loading translation cache: {e}")
            _translation_cache = {}
    else:
        logging.info("No translation cache file found. Starting with an empty cache.")
        _translation_cache = {}

def get_translation(lang_code: str, text: str) -> str | None:
    """
    Retrieves a translation from the cache.

    Args:
        lang_code: The language code (e.g., 'hi', 'ta').
        text: The English text to translate.

    Returns:
        The translated text if found in the cache, otherwise None.
    """
    return _translation_cache.get(lang_code, {}).get(text)

def add_translation(lang_code: str, text: str, translated_text: str):
    """
    Adds a new translation to the cache and saves it to the file.

    Args:
        lang_code: The language code.
        text: The original English text.
        translated_text: The translated text.
    """
    global _translation_cache
    if lang_code not in _translation_cache:
        _translation_cache[lang_code] = {}

    _translation_cache[lang_code][text] = translated_text

    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_translation_cache, f, ensure_ascii=False, indent=4)
    except IOError as e:
        logging.error(f"Error saving translation cache: {e}")
