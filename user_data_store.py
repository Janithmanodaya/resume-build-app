import firebase_client
import logging

logger = logging.getLogger(__name__)

def add_user(name: str, mobile: str):
    """Adds a user's name and mobile number to the Firebase Realtime Database."""
    if not name or not mobile:
        return

    success = firebase_client.store_user_data(name, mobile)
    if success:
        logger.info(f"Stored user '{name}' in Firebase.")
    else:
        logger.error(f"Failed to store user '{name}' in Firebase.")

def get_all_users() -> list[str]:
    """Returns a list of all users from the Firebase Realtime Database."""
    return firebase_client.get_all_users()
