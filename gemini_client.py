import google.generativeai as genai
from config import GEMINI_API_KEY
import logging
import json
import re

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
    model = genai.GenerativeModel("gemini-1.5-flash-latest")
except Exception as e:
    logging.error(f"Failed to configure Gemini: {e}")
    model = None

def enhance_summary(text: str, template_style: str = "modern") -> str | None:
    """
    Rewrites a user's summary into a more professional version using Gemini,
    with style-specific prompts.
    """
    if not model:
        logging.warning("Gemini model not available. Skipping enhancement.")
        return None

    if template_style == 'creative':
        prompt = f"Rewrite the following into a unique, creative, and compelling professional summary for a resume (2-4 sentences max). Use a slightly more personal and narrative tone. Original text: '{text}'"
    else: # Default to modern/professional
        prompt = f"Rewrite the following into a professional and impactful resume summary (2-4 sentences max): '{text}'"

    try:
        response = model.generate_content(prompt)
        return clean_markdown(response.text)
    except Exception as e:
        logging.error(f"Gemini API call failed for summary enhancement: {e}")
        return None


def enhance_experience(duties: list[str]) -> list[str] | None:
    """
    Rewrites job duties into strong, action-oriented bullet points.
    (This function is now intended for single items, but the name is kept for compatibility).
    """
    if not model:
        logging.warning("Gemini model not available. Skipping enhancement.")
        return None

    duties_str = "\n- ".join(duties)
    prompt = f"Rephrase these job duties into strong, action-oriented bullet points for a resume. Return only the bullet points:\n- {duties_str}"

    try:
        response = model.generate_content(prompt)
        enhanced_duties = [clean_markdown(line.strip().lstrip('- ').capitalize()) for line in response.text.strip().split('\n') if line.strip()]
        return enhanced_duties
    except Exception as e:
        logging.error(f"Gemini API call failed for experience enhancement: {e}")
        return None

def enhance_multiple_experiences(experiences: list[str]) -> list[str] | None:
    """
    Enhances a list of job experiences in a single batch API call.
    Each experience is a string like "Job Title, Company, Dates, Description".
    This function focuses on rewriting the description part of each experience.
    """
    if not model:
        logging.warning("Gemini model not available. Skipping enhancement.")
        return None

    # We create a numbered list of descriptions for the prompt
    descriptions_to_enhance = []
    for exp in experiences:
        parts = [p.strip() for p in exp.split(',')]
        descriptions_to_enhance.append(parts[-1] if len(parts) > 1 else exp)

    numbered_descriptions = "\n".join([f"{i+1}. {desc}" for i, desc in enumerate(descriptions_to_enhance)])

    prompt = (
        "Rewrite each of the following job descriptions into a strong, action-oriented bullet point for a resume. "
        "Return a numbered list where each number corresponds to the original description. "
        "Do not include the job title, company, or dates in your response.\n\n"
        f"{numbered_descriptions}"
    )

    try:
        response = model.generate_content(prompt)
        # Process the response, which should be a numbered list
        enhanced_descriptions = [clean_markdown(line.strip().lstrip('0123456789. ')) for line in response.text.strip().split('\n') if line.strip()]

        if len(enhanced_descriptions) != len(experiences):
            logging.warning("Batch enhancement returned a different number of items. Falling back to original.")
            return experiences # Fallback in case of parsing error

        # Reconstruct the original experience strings with the new descriptions
        final_experiences = []
        for i, exp in enumerate(experiences):
            parts = [p.strip() for p in exp.split(',')]
            if len(parts) > 1:
                parts[-1] = enhanced_descriptions[i]
                final_experiences.append(", ".join(parts))
            else:
                final_experiences.append(enhanced_descriptions[i])

        return final_experiences

    except Exception as e:
        logging.error(f"Gemini API call failed for batch experience enhancement: {e}")
        return None

def generate_about_me(user_data: dict) -> str | None:
    """
    Generates a short 'About Me' section based on the user's resume data.
    """
    if not model:
        logging.warning("Gemini model not available. Skipping 'About Me' generation.")
        return None

    # Construct a string representation of the user's current resume
    resume_text = f"""
    Name: {user_data.get('name', '')}
    Summary: {user_data.get('summary', '')}
    Skills: {', '.join(skill['name'] for skill in user_data.get('skills', []))}
    Experience: {' | '.join(user_data.get('experience', []))}
    Education: {' | '.join(user_data.get('education', []))}
    """

    prompt = (
        "You are a professional resume writer. Based on the following resume data, write a short, engaging 'About Me' section of 2-3 sentences. "
        "Focus on the key skills and experience to create a compelling narrative. The tone should be professional but personable.\n\n"
        f"**Resume Data:**\n{resume_text}\n\n"
        "**Generated 'About Me' Section:**"
    )

    try:
        response = model.generate_content(prompt)
        return clean_markdown(response.text.strip())
    except Exception as e:
        logging.error(f"Gemini API call failed for 'About Me' generation: {e}")
        return None


def tailor_resume_for_job(user_data: dict, job_description: str) -> dict | None:
    """
    Uses Gemini to tailor a resume for a specific job description.
    Returns a dictionary with a tailored summary and suggested skills.
    """
    if not model:
        logging.warning("Gemini model not available. Skipping tailoring.")
        return None

    # Construct a string representation of the user's current resume
    resume_text = f"""
    Current Summary: {user_data.get('summary', '')}
    Skills: {', '.join(skill['name'] for skill in user_data.get('skills', []))}
    Experience: {' | '.join(user_data.get('experience', []))}
    """

    prompt = (
        "You are an expert resume assistant. Based on the user's current resume and the provided job description, perform two tasks:\n"
        "1. Rewrite the professional summary to be perfectly tailored for the job. The new summary should be impactful and 2-4 sentences long.\n"
        "2. Identify up to 5 crucial skills or keywords from the job description that are missing from the user's current skill list.\n\n"
        "Return your response in a structured format with clear headings, like this:\n"
        "--- TAILORED SUMMARY ---\n"
        "[Your rewritten summary here]\n"
        "--- SUGGESTED SKILLS ---\n"
        "- [Skill 1]\n"
        "- [Skill 2]\n"
        "...\n\n"
        f"**User's Resume:**\n{resume_text}\n\n"
        f"**Job Description:**\n{job_description}"
    )

    try:
        response = model.generate_content(prompt)

        # Parse the structured response
        summary_part = clean_markdown(response.text.split("--- TAILORED SUMMARY ---")[1].split("--- SUGGESTED SKILLS ---")[0].strip())
        skills_part = response.text.split("--- SUGGESTED SKILLS ---")[1].strip()

        suggested_skills = [clean_markdown(skill.strip().lstrip('- ')) for skill in skills_part.split('\n') if skill.strip()]

        return {
            "tailored_summary": summary_part,
            "suggested_skills": suggested_skills,
        }

    except Exception as e:
        logging.error(f"Gemini API call failed for resume tailoring: {e}")
        return None


def parse_resume_data(text: str) -> dict | None:
    """
    Parses a single block of text to extract structured resume data using Gemini.
    """
    if not model:
        logging.warning("Gemini model not available. Skipping parsing.")
        return None

    prompt = (
        "You are an expert data extraction assistant. From the following text, extract the user's name, email, phone number, "
        "a professional summary, a list of skills (with a proficiency rating from 1-5 if available, otherwise default to 3), "
        "a list of work experiences, and a list of education entries. Return the data as a JSON object with the following keys: "
        "'name', 'email', 'phone', 'summary', 'skills' (as a list of objects with 'name' and 'rating' keys), "
        "'experience' (as a list of strings), and 'education' (as a list of strings).\n\n"
        "If a piece of information is not available, set its value to null.\n\n"
        f"Text to parse:\n---\n{text}\n---"
    )

    try:
        response = model.generate_content(prompt)
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
