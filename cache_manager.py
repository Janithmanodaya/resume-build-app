import json
import logging
import os
from collections import OrderedDict

CACHE_FILE = "translation_cache.json"
MAX_CACHE_SIZE = 1000  # Max number of entries to keep in the cache
_cache = OrderedDict()

def load_cache():
    """Loads the translation cache from the JSON file into memory."""
    global _cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                # Load into an OrderedDict to maintain insertion order
                _cache = OrderedDict(json.load(f))
                logging.info(f"Translation cache loaded from {CACHE_FILE} with {len(_cache)} items.")
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Failed to load cache file {CACHE_FILE}: {e}")
            _cache = OrderedDict()
    else:
        logging.info("Cache file not found. Starting with an empty cache.")
        _cache = OrderedDict()

def save_cache():
    """Saves the in-memory cache to the JSON file."""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False, indent=4)
    except IOError as e:
        logging.error(f"Failed to save cache to {CACHE_FILE}: {e}")

def get_from_cache(key: str) -> str | None:
    """
    Retrieves an item from the cache.
    Args:
        key: The key to look up (e.g., a tuple of (text, language)).
    Returns:
        The cached translation or None if not found.
    """
    # JSON keys must be strings, so convert the tuple key
    str_key = json.dumps(key)
    return _cache.get(str_key)

def add_to_cache(key: str, value: str):
    """
    Adds an item to the cache and saves it.
    If the cache exceeds MAX_CACHE_SIZE, the oldest item is removed.
    Args:
        key: The key for the cache entry.
        value: The value to cache.
    """
    global _cache
    # JSON keys must be strings
    str_key = json.dumps(key)

    if str_key in _cache:
        # Move to the end to mark as recently used
        _cache.move_to_end(str_key)

    _cache[str_key] = value

    # Enforce cache size limit (FIFO)
    if len(_cache) > MAX_CACHE_SIZE:
        _cache.popitem(last=False) # Remove the first (oldest) item

    save_cache()
