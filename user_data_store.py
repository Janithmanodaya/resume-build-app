import json
import os
import logging

logger = logging.getLogger(__name__)

DATA_FILE = 'generated_users.json'

def _load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def _save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def add_user(username: str):
    """Adds a username to the list of users who have generated a PDF."""
    if not username:
        return

    data = _load_data()
    if username not in data:
        data.append(username)
        _save_data(data)
        logger.info(f"Added user '{username}' to the data store.")

def get_all_users() -> list[str]:
    """Returns a list of all users who have generated a PDF."""
    return _load_data()
