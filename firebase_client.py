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
