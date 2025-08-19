import google.generativeai as genai
from config import GEMINI_API_KEY
import logging
import json
import re
import asyncio

def clean_markdown(text: str) -> str:
    """Removes common markdown formatting characters from a string."""
    if not isinstance(text, str):
        return text
    # Remove bold, italic, strikethrough, code
    text = re.sub(r'([*_`~])', '', text)
    # A simple way to handle links, just keep the text part: [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    return text

def clean_data_recursively(data):
    """Recursively cleans markdown from all string values in a nested data structure."""
    if isinstance(data, dict):
        return {k: clean_data_recursively(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_data_recursively(i) for i in data]
    elif isinstance(data, str):
        return clean_markdown(data)
    else:
        return data

# Configure the Gemini API client
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash-lite")
except Exception as e:
    logging.error(f"Failed to configure Gemini: {e}")
    model = None

async def generate_about_me(user_data: dict) -> str | None:
    """
    Generates a short 'About Me' section based on the user's resume data.
    """
    if not model:
        logging.warning("Gemini model not available. Skipping 'About Me' generation.")
        return None

    # Construct a string representation of the user's current resume
    resume_text = f"""
    Name: {user_data.get('name', '')}
    Skills: {', '.join(skill['name'] for skill in user_data.get('skills', []))}
    Experience: {' | '.join(user_data.get('experience', []))}
    Education: {' | '.join(user_data.get('education', []))}
    """

    prompt = (
        "You are a professional resume writer. Based on the following resume data, write a short, engaging 'About Me' section. "
        "It must be a short biography and limited to 50 words. "
        "Focus on the key skills and experience to create a compelling narrative. The tone should be professional but personable.\n\n"
        f"**Resume Data:**\n{resume_text}\n\n"
        "**Generated 'About Me' Section:**"
    )

    try:
        response = await model.generate_content_async(prompt)
        return clean_markdown(response.text.strip())
    except Exception as e:
        logging.error(f"Gemini API call failed for 'About Me' generation: {e}")
        return None

async def parse_resume_from_template(text: str) -> dict | None:
    """
    Parses a single block of text based on a template to extract structured resume data using Gemini.
    """
    if not model:
        logging.warning("Gemini model not available. Skipping parsing.")
        return None

    prompt = (
        "You are an expert data extraction assistant. From the following text, which is based on a template, extract the user's details. The fields to extract are:\n"
        "- Name\n"
        "- Birthday\n"
        "- Email\n"
        "- Phone\n"
        "- Web site\n"
        "- Address\n"
        "- Language\n"
        "- NIC Number\n"
        "- A list of skills (with a proficiency rating from 1-5)\n"
        "- A list of work experiences\n"
        "- A list of education entries\n\n"
        "Return the data as a JSON object with the following keys: 'name', 'birthday', 'email', 'phone', 'website', 'address', 'language', 'nic_number', 'skills' (as a list of objects with 'name' and 'rating' keys), 'experience' (as a list of strings), and 'education' (as a list of strings).\n\n"
        "If a piece of information is not available, set its value to null. Be flexible with the input format, as users might not follow the template perfectly.\n\n"
        f"Text to parse:\n---\n{text}\n---"
    )

    try:
        response = await model.generate_content_async(prompt)
        # Clean up the response to ensure it's valid JSON
        clean_response = response.text.strip().replace("```json", "").replace("```", "").strip()

        # Log the raw and cleaned response for debugging
        logging.info(f"Gemini raw response for parsing: {response.text}")
        logging.info(f"Gemini cleaned response for parsing: {clean_response}")

        parsed_data = json.loads(clean_response)
        return clean_data_recursively(parsed_data)

    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode JSON from Gemini response: {e}")
        logging.error(f"Response that failed parsing: {clean_response}")
        return None
    except Exception as e:
        logging.error(f"Gemini API call failed for data parsing: {e}")
        return None

async def humanize_text(text: str, target_language: str) -> str | None:
    """
    Rephrases the given text to be more natural and human-like using the Gemini API.
    """
    if not model or not text:
        return text

    prompt = (
        f"You are a language expert. Rephrase the following text in '{target_language}' to be more natural, fluent, and human-like. "
        "Do not change the meaning of the text. Only provide the rephrased text in your response.\n\n"
        f"**Original Text:**\n{text}\n\n"
        "**Rephrased Text:**"
    )

    try:
        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        logging.error(f"Gemini API call failed for text humanization: {e}")
        return text # Return the original text on failure
