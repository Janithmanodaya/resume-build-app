import logging
from enum import Enum

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)


import config
from aiohttp import web
import json
import translation_client
import gemini_client

# Initialize the Google Translate client
google_translate_client = translation_client.get_google_translate_client()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

EMOJI_MAP = {
    "name": "👤",
    "birthday": "🎂",
    "email": "📧",
    "phone": "📞",
    "website": "🌐",
    "address": "📍",
    "language": "🗣️",
    "nic_number": "🆔",
    "skills": "🛠️",
    "experience": "💼",
    "education": "🎓",
}

RESUME_TEMPLATE = """
Please copy the template below, fill in your details, and send it back in a single message.

**Template:**
Name: [Your Name]
Birthday: [Your Birthday]
Email: [Your Email]
Phone: [Your Phone Number]
Web site: [Your Website URL]
Address: [Your Address]
Language: [Your Language]
NIC Number: [Your NIC Number]

Experience 1:
[Your Job Title], [Company], [Start Date - End Date], [Description]

Experience 2:
[Your Job Title], [Company], [Start Date - End Date], [Description]

To add more experience entries, just add a new line like:
Experience 3: [Job Title], [Company], [Dates], [Description]

Education 1:
[Your Degree], [University], [Graduation Year]

Education 2:
[O/L or A/L], [School], [Year]

To add more education entries, just add a new line like:
Education 3: [Degree], [University], [Year]

Skills:
[Skill 1], [Rating 1-5]
[Skill 2], [Rating 1-5]
"""

import os
import asyncio
import tempfile
import firebase_client
import user_data_store
import image_utils

# Define conversation states using an Enum for clarity
class States(Enum):
    START = 0
    AWAITING_LANGUAGE_SELECTION = -2
    AWAITING_VERIFICATION_CODE = -1
    AWAITING_TEMPLATE_INPUT = 1
    AWAITING_PHOTO_CHOICE = 2
    UPLOADING_PHOTO = 3
    AWAITING_ACCENT_COLOR = 4
    AWAITING_TEMPLATE_SELECTION = 5
    AWAITING_REGENERATION = 6
    AWAITING_REVIEW_CHOICE = 7
    EDITING_PERSONAL_DETAILS = 8
    EDITING_EXPERIENCE = 9
    EDITING_EDUCATION = 10
    EDITING_SKILLS = 11


# --- START HANDLER ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts the user to select a language."""
    keyboard = [
        [InlineKeyboardButton(lang, callback_data=f"lang_{code}") for lang, code in list(config.LANGUAGES.items())[:2]],
        [InlineKeyboardButton(lang, callback_data=f"lang_{code}") for lang, code in list(config.LANGUAGES.items())[2:4]],
        [InlineKeyboardButton(lang, callback_data=f"lang_{code}") for lang, code in list(config.LANGUAGES.items())[4:6]],
        [InlineKeyboardButton(lang, callback_data=f"lang_{code}") for lang, code in list(config.LANGUAGES.items())[6:8]],
        [InlineKeyboardButton(lang, callback_data=f"lang_{code}") for lang, code in list(config.LANGUAGES.items())[8:10]],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await send_translated_message(
        update,
        context,
        "Please select your language:",
        reply_markup=reply_markup
    )
    return States.AWAITING_LANGUAGE_SELECTION

async def send_translated_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None, parse_mode=None):
    """
    Translates, humanizes, and sends a message to the user.
    """
    target_language = context.user_data.get('language', 'en') # Default to English

    # If the target language is English, no need to translate or humanize
    if target_language == 'en':
        if update.callback_query:
            await update.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return

    # 1. Translate the text
    translated_text = await translation_client.translate_text(text, target_language, google_translate_client)
    if not translated_text:
        translated_text = text # Fallback to original text

    # 2. Humanize the text (unless the language is Sinhala)
    humanized_text = translated_text # Default to the direct translation
    if target_language != 'si':
        humanized_text_from_gemini = await gemini_client.humanize_text(translated_text, target_language)
        if humanized_text_from_gemini:
            humanized_text = humanized_text_from_gemini # Use humanized text if successful

    # 3. Send the message
    if update.callback_query:
        await update.callback_query.message.reply_text(humanized_text, reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        await update.message.reply_text(humanized_text, reply_markup=reply_markup, parse_mode=parse_mode)

async def handle_language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the selected language and prompts for the verification code."""
    query = update.callback_query
    await query.answer()

    language_code = query.data.split('_')[1]
    context.user_data['language'] = language_code
    context.user_data['verification_attempts'] = 3

    await query.edit_message_text(text=f"Language set to {list(config.LANGUAGES.keys())[list(config.LANGUAGES.values()).index(language_code)]}.")

    return await request_verification_code(update, context)


async def request_verification_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts the user to enter their verification code."""
    await send_translated_message(
        update,
        context,
        "Welcome to the Resume Bot!\n\n"
        "Please enter your verification code to begin.",
        reply_markup=ReplyKeyboardRemove()
    )
    return States.AWAITING_VERIFICATION_CODE

async def handle_verification_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Verifies the user's code and starts the resume building process."""
    code = update.message.text.strip()

    if firebase_client.verify_and_delete_code(code):
        user_id = update.message.from_user.id
        chat_id = update.message.chat_id

        context.user_data['verified'] = True
        context.user_data['generation_attempts'] = 5
        context.user_data['user_id'] = user_id

        # Schedule a cleanup job for 6 hours later
        context.job_queue.run_once(timeout_cleanup, 6 * 3600, chat_id=chat_id, name=str(user_id))

        await send_translated_message(
            update,
            context,
            "Verification successful! Your session has started.\n\n"
            "You have 5 chances to generate a PDF resume."
        )

        await send_translated_message(
            update,
            context,
            RESUME_TEMPLATE,
            parse_mode="Markdown"
        )

        return States.AWAITING_TEMPLATE_INPUT
    else:
        context.user_data['verification_attempts'] -= 1
        attempts_left = context.user_data['verification_attempts']

        if attempts_left > 0:
            keyboard = [[InlineKeyboardButton("Contact Admin", url="https://t.me/+94788620859")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await send_translated_message(
                update,
                context,
                f"Invalid or expired code. You have {attempts_left} attempts remaining.\n\n"
                "Please try again or contact the admin to get a new code.",
                reply_markup=reply_markup
            )
            return States.AWAITING_VERIFICATION_CODE
        else:
            await send_translated_message(
                update,
                context,
                "You have used all your verification attempts. For security reasons, this session has been terminated. Please /start again later."
            )
            return await finish_conversation(update, context)


import gemini_client
import generator

async def handle_template_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Parses the user's template input and asks if they want to add a photo.
    """
    user_input = update.message.text

    # --- Language Check ---
    detected_language = await translation_client.detect_language(user_input, google_translate_client)
    if detected_language and detected_language != 'en':
        warnings = context.user_data.get('warnings', 0) + 1
        context.user_data['warnings'] = warnings

        if warnings >= 3:
            await send_translated_message(
                update,
                context,
                "You have repeatedly submitted information in a language other than English. "
                "For security reasons, this session has been terminated. Please /start again and follow the instructions."
            )
            return await finish_conversation(update, context)
        else:
            await send_translated_message(
                update,
                context,
                f"It looks like you provided your details in a language other than English. "
                f"Please provide all resume information in English only. This is warning {warnings} of 3."
            )
            return States.AWAITING_TEMPLATE_INPUT
    # --- End Language Check ---


    await send_translated_message(update, context, "Thank you. I am now processing your information with AI. This may take a moment...")

    # Call the new Gemini client function to parse the template
    parsed_data = await gemini_client.parse_resume_from_template(user_input)

    if not parsed_data:
        await send_translated_message(
            update,
            context,
            "I'm sorry, I couldn't extract the information from your text. "
            "Please try filling out the template again carefully."
        )
        return States.AWAITING_TEMPLATE_INPUT

    # Store the parsed data in user_data
    context.user_data.update(parsed_data)

    # Show the extracted data to the user
    extracted_data_message = "Here is the data I extracted from your template:\n\n"
    for key, value in parsed_data.items():
        emoji = EMOJI_MAP.get(key, "🔹")
        if value:
            if isinstance(value, list):
                extracted_data_message += f"{emoji} **{key.replace('_', ' ').capitalize()}:**\n"
                for item in value:
                    if isinstance(item, dict):
                        extracted_data_message += f"  - {item.get('name', '')} (Rating: {item.get('rating', 'N/A')})\n"
                    else:
                        extracted_data_message += f"  - {item}\n"
                extracted_data_message += "\n"
            else:
                extracted_data_message += f"{emoji} **{key.replace('_', ' ').capitalize()}:** {value}\n\n"

    await send_translated_message(update, context, extracted_data_message, parse_mode="Markdown")

    upload_text = "📷 Upload Photo"
    skip_text = "➡️ Skip Photo"

    target_language = context.user_data.get('language', 'en')
    if target_language != 'en':
        upload_text = await translation_client.translate_text(upload_text, target_language, google_translate_client)
        skip_text = await translation_client.translate_text(skip_text, target_language, google_translate_client)


    keyboard = [
        [InlineKeyboardButton(upload_text, callback_data='photo_upload')],
        [InlineKeyboardButton(skip_text, callback_data='photo_skip')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await send_translated_message(
        update,
        context,
        "Would you like to add a profile photo?",
        reply_markup=reply_markup,
    )
    return States.AWAITING_PHOTO_CHOICE

async def handle_photo_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's choice to upload or skip the photo."""
    query = update.callback_query
    await query.answer()

    choice = query.data

    if choice == 'photo_upload':
        await send_translated_message(update, context, "Okay, please upload your profile photo now.", reply_markup=ReplyKeyboardRemove())
        return States.UPLOADING_PHOTO
    else:  # 'photo_skip'
        return await skip_photo(update, context)

async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Skips the photo upload and moves to accent color selection."""
    context.user_data["photo_path"] = None
    await send_translated_message(update, context, "No problem. Let's move on to selecting an accent color.", reply_markup=ReplyKeyboardRemove())
    return await prompt_for_accent_color(update, context)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the photo and moves to accent color selection."""
    photo_file = await update.message.photo[-1].get_file()

    # Create a temporary directory for the user's session
    user_id = update.message.from_user.id
    temp_dir = os.path.join(tempfile.gettempdir(), "resume_bot", str(user_id))
    os.makedirs(temp_dir, exist_ok=True)

    file_path = os.path.join(temp_dir, "profile_photo.jpg")
    await photo_file.download_to_drive(file_path)

    context.user_data["photo_path"] = file_path

    await send_translated_message(update, context, "Photo received! Now, let's pick an accent color.")
    return await prompt_for_accent_color(update, context)

async def prompt_for_accent_color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the user to pick an accent color."""
    colors = {"Blue": "#3498db", "Green": "#2ecc71", "Red": "#e74c3c", "Purple": "#8e44ad"}
    keyboard = []

    target_language = context.user_data.get('language', 'en')

    row = []
    for color_name, color_code in colors.items():
        translated_name = color_name
        if target_language != 'en':
            translated_name = await translation_client.translate_text(color_name, target_language, google_translate_client)

        row.append(InlineKeyboardButton(translated_name, callback_data=f"color_{color_name}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_translated_message(
        update,
        context,
        "Please pick an accent color for your resume:",
        reply_markup=reply_markup,
    )
    return States.AWAITING_ACCENT_COLOR

async def select_color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the selected color and moves to template selection."""
    query = update.callback_query
    await query.answer()

    color_map = {
        "Blue": "#3498db",
        "Green": "#2ecc71",
        "Red": "#e74c3c",
        "Purple": "#8e44ad",
    }

    color_choice = query.data.split('_')[1]
    context.user_data["accent_color"] = color_map[color_choice]

    await query.edit_message_text(text=f"Great! You've chosen {color_choice}.")

    return await send_template_previews(update, context)

async def send_template_previews(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends the template previews to the user."""
    await send_translated_message(update, context, "Please choose a template from the following options:")

    for template_name in config.TEMPLATES.keys():
        image_path = f"sample/{template_name}.png"

        if os.path.exists(image_path):
            keyboard = [[InlineKeyboardButton("Select this template", callback_data=f"template_{template_name}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_photo(
                photo=open(image_path, 'rb'),
                reply_markup=reply_markup
            )
        else:
            logger.warning(f"Sample image for template '{template_name}' not found.")

    return States.AWAITING_TEMPLATE_SELECTION

async def handle_template_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's template selection."""
    query = update.callback_query
    await query.answer()

    template_name = query.data.split('_')[1]
    context.user_data['selected_template'] = template_name

    await query.edit_message_caption(caption=f"You have selected the '{template_name}' template.")

    keyboard = [
        [InlineKeyboardButton("Yes, review my data", callback_data='review_yes')],
        [InlineKeyboardButton("No, generate PDF now", callback_data='review_no')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await send_translated_message(update, context, "Would you like to review or edit your data before we generate the PDF?", reply_markup=reply_markup)

    return States.AWAITING_REVIEW_CHOICE

async def handle_review_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's choice to review data or generate the PDF."""
    query = update.callback_query
    await query.answer()

    if query.data == 'review_yes':
        return await show_review_menu(update, context)
    elif query.data == 'review_no':
        return await generate_and_send_pdf(update, context)
    elif query.data == 'edit_personal':
        return await edit_personal_details(update, context)
    elif query.data == 'edit_experience':
        return await edit_experience(update, context)
    elif query.data == 'edit_education':
        return await edit_education(update, context)
    elif query.data == 'edit_skills':
        return await edit_skills(update, context)

async def show_review_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays the review menu with options to edit different sections."""
    keyboard = [
        [InlineKeyboardButton("Edit Personal Details", callback_data='edit_personal')],
        [InlineKeyboardButton("Edit Experience", callback_data='edit_experience')],
        [InlineKeyboardButton("Edit Education", callback_data='edit_education')],
        [InlineKeyboardButton("Edit Skills", callback_data='edit_skills')],
        [InlineKeyboardButton("Looks Good, Generate PDF", callback_data='review_no')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = "Please select a section to edit, or click 'Generate PDF' if you are ready."

    await send_translated_message(update, context, message, reply_markup=reply_markup)

    return States.AWAITING_REVIEW_CHOICE

async def edit_personal_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Shows current personal details and prompts for edits."""
    query = update.callback_query
    await query.answer()

    personal_details = {
        "Name": context.user_data.get("name"),
        "Birthday": context.user_data.get("birthday"),
        "Email": context.user_data.get("email"),
        "Phone": context.user_data.get("phone"),
        "Web site": context.user_data.get("website"),
        "Address": context.user_data.get("address"),
        "Language": context.user_data.get("language"),
        "NIC Number": context.user_data.get("nic_number"),
    }

    message = "Here are your current personal details:\n\n"
    for key, value in personal_details.items():
        message += f"**{key}:** {value or 'Not set'}\n"

    message += "\nPlease send the updated details in the same format, or send 'yes' to skip."

    reply_markup = ReplyKeyboardMarkup([["Skip"]], one_time_keyboard=True, resize_keyboard=True)

    await send_translated_message(update, context, message, parse_mode="Markdown", reply_markup=reply_markup)
    return States.EDITING_PERSONAL_DETAILS

async def edit_experience(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Shows current experience and prompts for edits."""
    query = update.callback_query
    await query.answer()

    experience = context.user_data.get("experience", [])
    message = "Here is your current experience:\n\n"
    if experience:
        message += "\n".join(f"- {exp}" for exp in experience)
    else:
        message += "Not set."

    message += "\nPlease send the updated experience, with each entry on a new line. Or, send 'yes' to skip."

    reply_markup = ReplyKeyboardMarkup([["Skip"]], one_time_keyboard=True, resize_keyboard=True)

    await send_translated_message(update, context, message, parse_mode="Markdown", reply_markup=reply_markup)
    return States.EDITING_EXPERIENCE

async def edit_education(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Shows current education and prompts for edits."""
    query = update.callback_query
    await query.answer()

    education = context.user_data.get("education", [])
    message = "Here is your current education:\n\n"
    if education:
        message += "\n".join(f"- {edu}" for edu in education)
    else:
        message += "Not set."

    message += "\nPlease send the updated education, with each entry on a new line. Or, send 'yes' to skip."

    reply_markup = ReplyKeyboardMarkup([["Skip"]], one_time_keyboard=True, resize_keyboard=True)

    await send_translated_message(update, context, message, parse_mode="Markdown", reply_markup=reply_markup)
    return States.EDITING_EDUCATION

async def edit_skills(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Shows current skills and prompts for edits."""
    query = update.callback_query
    await query.answer()

    skills = context.user_data.get("skills", [])
    message = "Here are your current skills:\n\n"
    if skills:
        message += "\n".join(f"- {s['name']} (Rating: {s['rating']})" for s in skills)
    else:
        message += "Not set."

    message += "\nPlease send the updated skills, with each skill on a new line (e.g., Python, 5). Or, send 'yes' to skip."

    reply_markup = ReplyKeyboardMarkup([["Skip"]], one_time_keyboard=True, resize_keyboard=True)

    await send_translated_message(update, context, message, parse_mode="Markdown", reply_markup=reply_markup)
    return States.EDITING_SKILLS

async def handle_edited_personal_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's edited personal details."""
    if update.message.text.lower() in ['yes', 'skip']:
        await send_translated_message(update, context, "No changes made to personal details.", reply_markup=ReplyKeyboardRemove())
        return await show_review_menu(update, context)

    # This is a simplified parser. A more robust solution would be to use the AI again.
    # For now, we'll just assume the user provides the data in a key: value format.
    for line in update.message.text.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip().lower().replace(' ', '_')
            context.user_data[key] = value.strip()

    await send_translated_message(update, context, "Personal details updated.", reply_markup=ReplyKeyboardRemove())
    return await show_review_menu(update, context)

async def handle_edited_experience(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's edited experience."""
    if update.message.text.lower() in ['yes', 'skip']:
        await send_translated_message(update, context, "No changes made to experience.", reply_markup=ReplyKeyboardRemove())
        return await show_review_menu(update, context)

    context.user_data['experience'] = [exp.strip() for exp in update.message.text.split('\n')]
    await send_translated_message(update, context, "Experience updated.", reply_markup=ReplyKeyboardRemove())
    return await show_review_menu(update, context)

async def handle_edited_education(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's edited education."""
    if update.message.text.lower() in ['yes', 'skip']:
        await send_translated_message(update, context, "No changes made to education.", reply_markup=ReplyKeyboardRemove())
        return await show_review_menu(update, context)

    context.user_data['education'] = [edu.strip() for edu in update.message.text.split('\n')]
    await send_translated_message(update, context, "Education updated.", reply_markup=ReplyKeyboardRemove())
    return await show_review_menu(update, context)

async def handle_edited_skills(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's edited skills."""
    if update.message.text.lower() in ['yes', 'skip']:
        await send_translated_message(update, context, "No changes made to skills.", reply_markup=ReplyKeyboardRemove())
        return await show_review_menu(update, context)

    skills = []
    for line in update.message.text.split('\n'):
        if ',' in line:
            name, rating = line.split(',', 1)
            skills.append({'name': name.strip(), 'rating': int(rating.strip())})
    context.user_data['skills'] = skills
    await send_translated_message(update, context, "Skills updated.", reply_markup=ReplyKeyboardRemove())
    return await show_review_menu(update, context)


async def generate_and_send_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE, exclude_template: str = None) -> int:
    """Helper function to generate, send, and clean up the PDF."""
    message_sender = update.callback_query.message if update.callback_query else update.message

    # Check if the user is verified and has attempts left
    if not context.user_data.get('verified') or context.user_data.get('generation_attempts', 0) <= 0:
        await send_translated_message(
            update,
            context,
            "You have no PDF generation attempts left. Please /start a new session.",
            reply_markup=ReplyKeyboardRemove()
        )
        return await finish_conversation(update, context)

    await send_translated_message(update, context, "I'm now generating your resume...")

    logger.info(f"Final user data: {context.user_data}")
    
    # The generator now returns a tuple: (path, template_name)
    selected_template = context.user_data.get('selected_template')
    pdf_generation_result = await generator.generate_pdf(context.user_data, selected_template=selected_template, exclude_template=exclude_template)

    if pdf_generation_result:
        pdf_path, template_name = pdf_generation_result
        context.user_data['last_template'] = template_name # Save the used template
        
        # Decrement generation attempts
        context.user_data['generation_attempts'] -= 1
        attempts_left = context.user_data['generation_attempts']
        
        caption = f"Here is your generated resume! You have {attempts_left} attempts remaining."
        translated_caption = await translation_client.translate_text(caption, context.user_data.get('language', 'en'), google_translate_client)
        humanized_caption = await gemini_client.humanize_text(translated_caption, context.user_data.get('language', 'en'))

        await message_sender.reply_document(
            document=open(pdf_path, 'rb'),
            filename=f"{context.user_data.get('name', 'resume')}.pdf",
            caption=humanized_caption
        )
        os.remove(pdf_path)

        # Log the user who generated the PDF
        user_data_store.add_user(context.user_data.get('name'))

        # Only offer regeneration if the user has attempts left
        target_language = context.user_data.get('language', 'en')

        regenerate_text = "🎨 Regenerate with New Design"
        finish_text = "✅ Finish"

        if target_language != 'en':
            regenerate_text = await translation_client.translate_text(regenerate_text, target_language, google_translate_client)
            finish_text = await translation_client.translate_text(finish_text, target_language, google_translate_client)

        if attempts_left > 0:
            keyboard = [[InlineKeyboardButton(regenerate_text, callback_data='regenerate_yes')], [InlineKeyboardButton(finish_text, callback_data='regenerate_no')]]
        else:
            keyboard = [[InlineKeyboardButton(finish_text, callback_data='regenerate_no')]]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await send_translated_message(
            update,
            context,
            "What would you like to do next?",
            reply_markup=reply_markup,
        )
        return States.AWAITING_REGENERATION

    else:
        await send_translated_message(update, context, "Sorry, something went wrong while generating your PDF.")
        # Clean up and end conversation on failure
        return await finish_conversation(update, context)


async def handle_regeneration_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's choice to regenerate or finish."""
    query = update.callback_query
    await query.answer()

    choice = query.data

    if choice == 'regenerate_yes':
        if context.user_data.get('generation_attempts', 0) > 0:
            await send_translated_message(update, context, "Let's pick a new design.")
            return await send_template_previews(update, context)
        else:
            await send_translated_message(
                update,
                context,
                "You have no more PDF generation attempts left. Please /start a new session to continue."
            )
            return await finish_conversation(update, context)
    else:  # 'regenerate_no'
        return await finish_conversation(update, context)


def _remove_job_if_exists(name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True

async def _cleanup_session(context: ContextTypes.DEFAULT_TYPE):
    """Cleans up all user data and removes any scheduled jobs."""
    if 'user_id' in context.user_data:
        _remove_job_if_exists(str(context.user_data['user_id']), context)

    if context.user_data.get('photo_path'):
        local_photo_path = context.user_data['photo_path'].replace('file://', '')
        if os.path.exists(local_photo_path):
            try:
                os.remove(local_photo_path)
                logger.info(f"Cleaned up photo: {local_photo_path}")
            except OSError as e:
                logger.error(f"Error cleaning up photo {local_photo_path}: {e}")

    context.user_data.clear()

async def timeout_cleanup(context: ContextTypes.DEFAULT_TYPE):
    """Sends a timeout message and cleans up the session."""
    # We can't use the helper here as we don't have the update object, so we send in English.
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text="Your session has timed out due to 6 hours of inactivity. Please /start again."
    )
    await _cleanup_session(context)


async def finish_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Clears user data and ends the conversation."""
    await send_translated_message(update, context, "Great! Feel free to start over any time with /start.", reply_markup=ReplyKeyboardRemove())
    await _cleanup_session(context)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await send_translated_message(update, context, "Operation cancelled.", reply_markup=ReplyKeyboardRemove())
    await _cleanup_session(context)
    return ConversationHandler.END


async def invalid_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles any input that is not appropriate for the current state."""
    await send_translated_message(
        update,
        context,
        "Sorry, I was expecting different input. Please follow the instructions or type /cancel to start over."
    )
    # This does not change the state
    return


async def fallback_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catches any button clicks that don't match a state."""
    query = update.callback_query
    await query.answer()
    logger.warning(f"Fallback callback handler triggered for data: {query.data}")
    await send_translated_message(
        update,
        context,
        "Something went wrong! This button is not active. Please type /start to begin again."
    )
    return ConversationHandler.END


import time

async def cleanup_old_files(context: ContextTypes.DEFAULT_TYPE):
    """
    Cleans up old temporary files (photos and PDFs) that are older than 6 hours.
    """
    now = time.time()
    six_hours_ago = now - (6 * 3600)

    # Cleanup PDFs
    pdf_dir = "/tmp/resume_bot/pdfs"
    if os.path.exists(pdf_dir):
        for filename in os.listdir(pdf_dir):
            filepath = os.path.join(pdf_dir, filename)
            if os.path.isfile(filepath):
                file_mod_time = os.path.getmtime(filepath)
                if file_mod_time < six_hours_ago:
                    os.remove(filepath)
                    logger.info(f"Cleaned up old PDF: {filepath}")

    # Cleanup photos
    photo_base_dir = os.path.join(tempfile.gettempdir(), "resume_bot")
    if os.path.exists(photo_base_dir):
        for user_dir in os.listdir(photo_base_dir):
            user_dir_path = os.path.join(photo_base_dir, user_dir)
            if os.path.isdir(user_dir_path):
                for filename in os.listdir(user_dir_path):
                    filepath = os.path.join(user_dir_path, filename)
                    if os.path.isfile(filepath):
                        file_mod_time = os.path.getmtime(filepath)
                        if file_mod_time < six_hours_ago:
                            os.remove(filepath)
                            logger.info(f"Cleaned up old photo: {filepath}")


async def get_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends the list of users who have generated a PDF to the admin."""
    user_id = update.message.from_user.id
    if str(user_id) == config.ADMIN_CHAT_ID:
        users = user_data_store.get_all_users()
        if users:
            message = "Users who have generated a PDF:\n\n" + "\n".join(users)
        else:
            message = "No users have generated a PDF yet."
        await update.message.reply_text(message)
    else:
        await update.message.reply_text("You are not authorized to use this command.")


async def telegram_webhook_handler(request: web.Request) -> web.Response:
    """Handle incoming Telegram updates by passing them to the bot application."""
    application = request.app["bot"]
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return web.Response()
    except json.JSONDecodeError:
        logger.error("Unable to parse JSON from Telegram update.")
        return web.Response(body=b"Unable to parse JSON", status=400)


async def health_check_handler(_: web.Request) -> web.Response:
    """A simple health check endpoint for the deployment platform."""
    return web.Response(text="OK")


async def root_handler(_: web.Request) -> web.Response:
    """A simple root endpoint to make site alive."""
    return web.Response(text="OK")


def prepare_sample_images():
    """
    Checks if sample images exist, and if not, creates them by watermarking the original images.
    """
    sample_dir = 'sample'
    image_dir = 'image'

    if not os.path.exists(sample_dir):
        os.makedirs(sample_dir)

    for template_name in config.TEMPLATES.keys():
        sample_image_path = f"{sample_dir}/{template_name}.png"

        if not os.path.exists(sample_image_path):
            original_image_path_jpg = f"{image_dir}/{template_name}.jpg"
            original_image_path_png = f"{image_dir}/{template_name}.png"

            original_image_path = None
            if os.path.exists(original_image_path_jpg):
                original_image_path = original_image_path_jpg
            elif os.path.exists(original_image_path_png):
                original_image_path = original_image_path_png

            if original_image_path:
                logger.info(f"Generating sample image for {template_name}...")
                image_utils.add_text_to_image(
                    original_image_path,
                    template_name.capitalize(),
                    sample_image_path
                )
            else:
                logger.warning(f"Original image for template '{template_name}' not found in 'image' directory.")


async def on_startup(app: web.Application):
    """
    Actions to take on application startup.
    - Set up the bot and its handlers.
    - Set the webhook.
    - Start the bot.
    """
    # Initialize Firebase
    firebase_client.initialize_firebase()

    # Prepare sample images
    prepare_sample_images()

    application = Application.builder().token(config.TELEGRAM_TOKEN).build()

    # Conversation handler setup
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            States.AWAITING_LANGUAGE_SELECTION: [CallbackQueryHandler(handle_language_selection, pattern='^lang_')],
            States.AWAITING_VERIFICATION_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_verification_code)],
            States.AWAITING_TEMPLATE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_template_input)],
            States.AWAITING_PHOTO_CHOICE: [CallbackQueryHandler(handle_photo_choice, pattern='^photo_')],
            States.UPLOADING_PHOTO: [MessageHandler(filters.PHOTO, handle_photo)],
            States.AWAITING_ACCENT_COLOR: [CallbackQueryHandler(select_color, pattern='^color_')],
            States.AWAITING_TEMPLATE_SELECTION: [CallbackQueryHandler(handle_template_selection, pattern='^template_')],
            States.AWAITING_REVIEW_CHOICE: [CallbackQueryHandler(handle_review_choice, pattern='^review_|^edit_')],
            States.EDITING_PERSONAL_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edited_personal_details)],
            States.EDITING_EXPERIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edited_experience)],
            States.EDITING_EDUCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edited_education)],
            States.EDITING_SKILLS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edited_skills)],
            States.AWAITING_REGENERATION: [CallbackQueryHandler(handle_regeneration_choice, pattern='^regenerate_')],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.TEXT & ~filters.COMMAND, invalid_input)],
    )
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("data", get_data))

    # Store the application instance in the aiohttp app context
    app["bot"] = application
    
    # Schedule the cleanup job
    application.job_queue.run_repeating(cleanup_old_files, interval=900, first=10) # 15 minutes

    # Initialize the bot, set the webhook, and start the bot
    await application.initialize()
    webhook_url = os.environ.get("WEBHOOK_URL", "").rstrip("/")
    if not webhook_url:
        logger.error("WEBHOOK_URL environment variable not set! Webhook not set.")
        return
        
    await application.bot.set_webhook(
        url=f"{webhook_url}/{config.TELEGRAM_TOKEN}",
        allowed_updates=Update.ALL_TYPES,
        secret_token=config.SECRET_TOKEN
    )
    await application.start()
    logger.info("Bot started and webhook is set.")


async def on_shutdown(app: web.Application):
    """Actions to take on application shutdown."""
    logger.info("Shutting down the bot...")
    await app["bot"].stop()
    await app["bot"].shutdown()
    logger.info("Bot has been shut down.")


if __name__ == "__main__":
    a_app = web.Application()
    
    # Register startup and shutdown handlers
    a_app.on_startup.append(on_startup)
    a_app.on_shutdown.append(on_shutdown)
    
    # Register webhook and health check handlers
    a_app.router.add_post(f"/{config.TELEGRAM_TOKEN}", telegram_webhook_handler)
    a_app.router.add_get("/health", health_check_handler)
    a_app.router.add_get("/", root_handler)

    # Get port from environment variables
    port = int(os.environ.get("PORT", 8080))
    
    logger.info(f"Starting aiohttp server on port {port}...")
    web.run_app(a_app, host="0.0.0.0", port=port)
