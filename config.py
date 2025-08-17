# config.py
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    raise ValueError("API keys not found! Please check your .env file.")

# You can add other settings here, like template names
TEMPLATES = {
    "modern": "resume_bot/templates/modern.html",
    "creative": "resume_bot/templates/creative.html",
    "template1": "resume_bot/templates/template1.html",
    "template2": "resume_bot/templates/template2.html",
    "template3": "resume_bot/templates/template3.html",
    "template4": "resume_bot/templates/template4.html",
    "template5": "resume_bot/templates/template5.html",
    "template6": "resume_bot/templates/template6.html",
    "template7": "resume_bot/templates/template7.html",
    "template8": "resume_bot/templates/template8.html",
    "template9": "resume_bot/templates/template9.html",
    "template10": "resume_bot/templates/template10.html",
    "template11": "resume_bot/templates/template11.html",
}
ACCENT_COLORS = ["#3498db", "#2ecc71", "#e74c3c", "#8e44ad"] # Blue, Green, Red, Purple
