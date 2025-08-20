import firebase_admin
from firebase_admin import credentials, db
import os
import logging

logger = logging.getLogger(__name__)

import json

def initialize_firebase():
    """
    Initializes the Firebase Admin SDK using credentials from environment variables.
    """
    try:
        # Check if the app is already initialized
        if not firebase_admin._apps:
            cred_json_str = os.environ.get("FIREBASE_CREDENTIALS_JSON")
            if not cred_json_str:
                logger.error("FIREBASE_CREDENTIALS_JSON environment variable not set.")
                return

            cred_json = json.loads(cred_json_str)

            cred = credentials.Certificate(cred_json)
            firebase_admin.initialize_app(cred, {
                'databaseURL': os.environ.get("FIREBASE_DATABASE_URL")
            })
            logger.info("Firebase app initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")


def verify_and_delete_code(code: str) -> bool:
    """
    Verifies a code against the 'resumedb' path in Firebase Realtime Database.
    If the code exists, it deletes it and returns True. Otherwise, returns False.

    Args:
        code: The verification code to check.

    Returns:
        True if the code was valid and deleted, False otherwise.
    """
    if not firebase_admin._apps:
        logger.warning("Firebase not initialized. Cannot verify code.")
        return False

    try:
        ref = db.reference('resumedb')
        all_codes = ref.get()

        if not all_codes:
            logger.warning("No codes found in the database.")
            return False

        for push_key, data in all_codes.items():
            if isinstance(data, dict) and data.get('key') == code:
                # Code found, delete it from the database
                ref.child(push_key).delete()
                logger.info(f"Verification code '{code}' successful. Key '{push_key}' deleted.")
                return True

        logger.info(f"Verification code '{code}' not found.")
        return False
    except Exception as e:
        logger.error(f"Error during Firebase code verification: {e}")
        return False


def store_user_data(name: str, mobile: str) -> bool:
    """
    Stores user data (name and mobile) in the 'verified_users' path in Firebase Realtime Database.

    Args:
        name: The user's name.
        mobile: The user's mobile number.

    Returns:
        True if the data was stored successfully, False otherwise.
    """
    if not firebase_admin._apps:
        logger.warning("Firebase not initialized. Cannot store user data.")
        return False

    try:
        ref = db.reference('verified_users')
        ref.push({
            'name': name,
            'mobile': mobile
        })
        logger.info(f"Stored user data for '{name}' successfully.")
        return True
    except Exception as e:
        logger.error(f"Error storing user data to Firebase: {e}")
        return False


def get_all_users() -> list[str]:
    """
    Retrieves a list of all users from the 'verified_users' path in Firebase Realtime Database.

    Returns:
        A list of strings, where each string is a user's name and mobile number.
    """
    if not firebase_admin._apps:
        logger.warning("Firebase not initialized. Cannot get user data.")
        return []

    try:
        ref = db.reference('verified_users')
        users = ref.get()
        if users:
            return [f"{user.get('name', 'N/A')} - {user.get('mobile', 'N/A')}" for user in users.values()]
        return []
    except Exception as e:
        logger.error(f"Error getting user data from Firebase: {e}")
        return []
