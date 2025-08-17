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

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


import os
import asyncio
import tempfile

# Define conversation states using an Enum for clarity
class States(Enum):
    START = 0
    SELECTING_TEMPLATE = 1
    SELECTING_COLOR = 2
    AWAITING_PHOTO_CHOICE = 3
    UPLOADING_PHOTO = 4
    GETTING_NAME = 5
    GETTING_CONTACTS = 6
    GETTING_SUMMARY = 7
    AWAITING_SUMMARY_APPROVAL = 8
    GETTING_SKILLS = 9
    GETTING_EXPERIENCE = 10
    GETTING_EDUCATION = 11
    ASKING_TAILOR = 12
    GETTING_JOB_DESCRIPTION = 13
    AWAITING_TAILOR_APPROVAL = 14
    GENERATING_PDF = 15
    GETTING_SMART_INPUT = 16
    AWAITING_SMART_APPROVAL = 17
    CHOOSING_INPUT_METHOD = 18
    AWAITING_REGENERATION = 19
    ASK_FOR_REVIEW = 20


# --- START HANDLER ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks for an accent color."""
    reply_keyboard = [["Blue", "Green"], ["Red", "Purple"]]

    await update.message.reply_text(
        "Welcome to the Resume Bot! Let's create your resume.\n\n"
        "A random template will be selected for you.\n\n"
        "First, pick an accent color:",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
    )
    return States.SELECTING_COLOR


# --- COLOR SELECTION ---
async def select_color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the selected color and asks the user if they want to add a photo."""
    color_map = {
        "Blue": "#3498db",
        "Green": "#2ecc71",
        "Red": "#e74c3c",
        "Purple": "#8e44ad",
    }

    color_choice = update.message.text.strip().capitalize()
    if color_choice not in color_map:
        await update.message.reply_text(
            "Invalid choice. Please select from Blue, Green, Red, or Purple."
        )
        return States.SELECTING_COLOR

    context.user_data["accent_color"] = color_map[color_choice]

    reply_keyboard = [["📷 Upload Photo", "➡️ Skip Photo"]]

    await update.message.reply_text(
        f"Great! You've chosen {color_choice} as the accent color.\n\n"
        "Would you like to add a profile photo?",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
    )
    return States.AWAITING_PHOTO_CHOICE


async def handle_photo_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's choice to upload or skip the photo."""
    choice = update.message.text

    if "📷 Upload Photo" in choice:
        await update.message.reply_text("Okay, please upload your profile photo now.", reply_markup=ReplyKeyboardRemove())
        return States.UPLOADING_PHOTO
    else:  # '➡️ Skip Photo'
        return await skip_photo(update, context)


async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Skips the photo upload and asks for input method."""
    context.user_data["photo_path"] = None
    await update.message.reply_text("No problem. Let's move on.", reply_markup=ReplyKeyboardRemove())
    return await prompt_for_input_method(update, context)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the photo and asks for input method."""
    photo_file = await update.message.photo[-1].get_file()
    
    # Create a temporary directory for the user's session
    user_id = update.message.from_user.id
    temp_dir = os.path.join(tempfile.gettempdir(), "resume_bot", str(user_id))
    os.makedirs(temp_dir, exist_ok=True)
    
    file_path = os.path.join(temp_dir, "profile_photo.jpg")
    await photo_file.download_to_drive(file_path)
    
    context.user_data["photo_path"] = file_path
    
    await update.message.reply_text("Photo received!")
    return await prompt_for_input_method(update, context)


async def prompt_for_input_method(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the user how they want to provide their resume information."""
    reply_keyboard = [["📝 Step-by-step", "🤖 Smart Paste (AI)"]]

    await update.message.reply_text(
        "How would you like to provide your resume information?",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
    )
    return States.CHOOSING_INPUT_METHOD


async def handle_input_method_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's choice of input method."""
    choice = update.message.text

    if "Step-by-step" in choice:
        await update.message.reply_text("Great! Let's go step-by-step. What is your full name?", reply_markup=ReplyKeyboardRemove())
        return States.GETTING_NAME
    else:  # "Smart Paste (AI)"
        await update.message.reply_text(
            "Excellent choice! Please paste your entire resume content below in a single message.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return States.GETTING_SMART_INPUT


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the name and asks for contact info."""
    user_input = update.message.text
    if not context.user_data.get('review_mode'):
        context.user_data["name"] = user_input
    elif user_input.lower() not in ['yes', 'skip']:
        context.user_data["name"] = user_input

    # Transition to the next step
    if context.user_data.get('review_mode'):
        prompt = (f"Current contacts: `{context.user_data.get('email', 'N/A')}, {context.user_data.get('phone', 'N/A')}`.\n"
                  "Reply 'yes' to keep, 'skip' to ignore, or send new contact info.")
    else:
        prompt = "Thanks! Now, please provide your email and phone number.\n\n**Example:**\njohn.doe@email.com, 123-456-7890"

    await update.message.reply_text(prompt, parse_mode="Markdown")
    return States.GETTING_CONTACTS


from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove

async def get_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores contact info and asks for a summary."""
    user_input = update.message.text
    
    if context.user_data.get('review_mode'):
        if user_input.lower() not in ['yes', 'skip']:
            if ',' not in user_input:
                await update.message.reply_text("Invalid format. Please provide both email and phone, separated by a comma.", parse_mode="Markdown")
                return States.GETTING_CONTACTS
            contacts = [item.strip() for item in user_input.split(',')]
            context.user_data["email"] = contacts[0]
            context.user_data["phone"] = contacts[1]
    else:
        contacts = [item.strip() for item in user_input.split(',')]
        context.user_data["email"] = contacts[0] if len(contacts) > 0 else ""
        context.user_data["phone"] = contacts[1] if len(contacts) > 1 else ""

    # Transition to the next step
    if context.user_data.get('review_mode'):
        prompt = (f"Current summary:\n\n'_{context.user_data.get('summary', 'N/A')}'_\n\n"
                  "Reply 'yes' to keep, 'skip' to ignore, or send a new summary.")
    else:
        prompt = "Contact info saved. Now, please write a professional summary about yourself."

    await update.message.reply_text(prompt, parse_mode="Markdown")
    return States.GETTING_SUMMARY


import gemini_client

async def get_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the summary, gets AI enhancement, and asks for approval."""
    user_input = update.message.text
    if context.user_data.get('review_mode'):
        if user_input.lower() in ['yes', 'skip']:
            # If user confirms or skips, move to the next section
            return await start_getting_skills(update, context)
    
    original_summary = user_input
    context.user_data["original_summary"] = original_summary
    
    await update.message.reply_text("Thanks. I'm now using AI to enhance your summary...")
    
    enhanced_summary = gemini_client.enhance_summary(original_summary)
    
    if enhanced_summary:
        context.user_data["enhanced_summary"] = enhanced_summary
        
        reply_keyboard = [["✅ Use AI Version", "✍️ Keep My Version"]]
        
        await update.message.reply_text(
            "Here is the AI-enhanced version of your summary:\n\n"
            f"**AI Version:**\n_{enhanced_summary}_\n\n"
            f"**Your Version:**\n_{original_summary}_\n\n"
            "Which version would you like to use?",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="Markdown"
        )
        return States.AWAITING_SUMMARY_APPROVAL
    else:
        # If AI enhancement fails, just use the original and move on
        context.user_data["summary"] = original_summary
        await update.message.reply_text(
            "AI enhancement failed. Using your original summary. Let's move on to skills."
        )
        # Fall through to the next step
        return await start_getting_skills(update, context)


async def handle_summary_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's choice for the summary and asks for skills."""
    choice = update.message.text
    
    if "✅ Use AI Version" in choice:
        context.user_data["summary"] = context.user_data["enhanced_summary"]
        await update.message.reply_text("Great, I've saved the AI-enhanced summary.", reply_markup=ReplyKeyboardRemove())
    else:
        context.user_data["summary"] = context.user_data["original_summary"]
        await update.message.reply_text("Okay, I've saved your original summary.", reply_markup=ReplyKeyboardRemove())
        
    return await start_getting_skills(update, context)


async def start_getting_skills(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Shared function to start the skill collection process."""
    message_sender = update.callback_query.message if update.callback_query else update.message

    if context.user_data.get('review_mode') and context.user_data.get('skills'):
        skills_list = "\n".join([f"- {s['name']} (Rating: {s['rating']})" for s in context.user_data['skills']])
        prompt = (f"Here are your current skills:\n{skills_list}\n\n"
                  "To keep these, click 'Done'. To clear this list and add new skills, just start adding them now.")
        # In review mode, we don't clear the list until the user adds a new item.
    else:
        prompt = ("Now, list your skills and rate your proficiency from 1 to 5.\n\n"
                  "**Format:** `Skill Name, Rating`\n"
                  "**Example:** `Python, 5`\n\n"
                  "Enter one skill at a time. Click 'Done' when you are finished.")
        context.user_data["skills"] = []

    reply_keyboard = [["Done"]]
    await message_sender.reply_text(
        prompt,
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="e.g., Python, 5"
        ),
        parse_mode="Markdown"
    )
    return States.GETTING_SKILLS


async def get_skill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores a skill and its rating, then asks for the next one."""
    # In review mode, the first new entry clears the old list.
    if context.user_data.get('review_mode') and 'skills_cleared_in_review' not in context.user_data:
        context.user_data['skills'] = []
        context.user_data['skills_cleared_in_review'] = True
        
    parts = [p.strip() for p in update.message.text.split(',')]
    if len(parts) == 2 and parts[1].isdigit() and 1 <= int(parts[1]) <= 5:
        skill_name = parts[0]
        skill_rating = int(parts[1])
        context.user_data["skills"].append({"name": skill_name, "rating": skill_rating})
        await update.message.reply_text(f"'{skill_name}' with rating {skill_rating} added. Enter another skill, or click 'Done'.")
    else:
        await update.message.reply_text(
            "Invalid format. Please use the format: `Skill Name, Rating` (e.g., Python, 5). The rating must be a number between 1 and 5."
        )
    return States.GETTING_SKILLS


async def skills_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ends the skill section and asks for experience."""
    # Clean up the review flag
    if 'skills_cleared_in_review' in context.user_data:
        del context.user_data['skills_cleared_in_review']
        
    await update.message.reply_text(
        "Skills section complete! Now, let's add your work experience.",
        reply_markup=ReplyKeyboardRemove(),
    )
    
    if context.user_data.get('review_mode') and context.user_data.get('experience'):
        exp_list = "\n\n".join(context.user_data['experience'])
        prompt = (f"Here is your current work experience:\n{exp_list}\n\n"
                  "To keep it, click 'Done'. To clear and re-enter, just start typing your first job entry.")
    else:
        prompt = ("Please enter one job at a time using this format:\n"
                  "`Job Title, Company, Start Date - End Date, Key responsibilities or achievements`\n\n"
                  "**Example:**\n"
                  "Software Engineer, Google, 2020 - Present, Developed a scalable web application that increased user engagement by 15%.\n\n"
                  "Click 'Done' when you are finished.")
        context.user_data["experience"] = []

    reply_keyboard = [["Done"]]
    await update.message.reply_text(
        prompt,
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="Enter a job"
        ),
        parse_mode="Markdown"
    )
    return States.GETTING_EXPERIENCE


async def get_experience(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores an experience entry and asks for the next one."""
    if context.user_data.get('review_mode') and 'experience_cleared_in_review' not in context.user_data:
        context.user_data['experience'] = []
        context.user_data['experience_cleared_in_review'] = True
        
    experience_text = update.message.text
    context.user_data["experience"].append(experience_text)
    await update.message.reply_text(f"Experience added. Enter another one, or click 'Done'.")
    return States.GETTING_EXPERIENCE


async def experience_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ends the experience section, runs batch enhancement, and asks for education."""
    if 'experience_cleared_in_review' in context.user_data:
        del context.user_data['experience_cleared_in_review']
        
    await update.message.reply_text(
        "Experience section complete! I will now enhance the descriptions with AI...",
        reply_markup=ReplyKeyboardRemove(),
    )

    original_experiences = context.user_data.get("experience", [])
    if original_experiences:
        enhanced_experiences = gemini_client.enhance_multiple_experiences(original_experiences)
        if enhanced_experiences:
            context.user_data["experience"] = enhanced_experiences
            await update.message.reply_text("Descriptions enhanced successfully!")
        else:
            await update.message.reply_text("AI enhancement failed, using your original descriptions.")

    # Proceed to the next step
    if context.user_data.get('review_mode') and context.user_data.get('education'):
        edu_list = "\n\n".join(context.user_data['education'])
        prompt = (f"Here is your current education:\n{edu_list}\n\n"
                  "To keep it, click 'Done'. To clear and re-enter, just start typing your first education entry.")
    else:
        prompt = ("Please enter one education entry at a time using this format:\n"
                  "`Degree, University, Graduation Year`\n\n"
                  "**Example:**\n"
                  "B.S. in Computer Science, MIT, 2020\n\n"
                  "Click 'Done' when you are finished.")
        context.user_data["education"] = []
        
    reply_keyboard = [["Done"]]
    await update.message.reply_text(
        prompt,
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="Enter education"
        ),
        parse_mode="Markdown"
    )
    return States.GETTING_EDUCATION


async def get_education(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores an education entry and asks for the next one."""
    if context.user_data.get('review_mode') and 'education_cleared_in_review' not in context.user_data:
        context.user_data['education'] = []
        context.user_data['education_cleared_in_review'] = True
        
    education_text = update.message.text
    context.user_data["education"].append(education_text)
    await update.message.reply_text(f"Education entry added. Enter another one, or click 'Done'.")
    return States.GETTING_EDUCATION


import generator

async def education_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ends data collection and asks if the user wants to review their data."""
    if 'education_cleared_in_review' in context.user_data:
        del context.user_data['education_cleared_in_review']
        
    await update.message.reply_text(
        "All information collected!",
        reply_markup=ReplyKeyboardRemove(),
    )
    
    reply_keyboard = [["✍️ Yes, review my data", "👍 No, looks good"]]

    await update.message.reply_text(
        "Before we generate the PDF, would you like to review and edit any of the information you've provided?",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
    )
    return States.ASK_FOR_REVIEW


async def handle_review_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's choice to review their data or not."""
    choice = update.message.text

    if "✍️ Yes, review my data" in choice:
        context.user_data['review_mode'] = True
        name = context.user_data.get('name')
        prompt = f"I found the name: `{name}`.\nPlease send the correct name, or send this one to confirm." if name else "What is your full name?"
        
        await update.message.reply_text(
            "No problem. Let's review the extracted information step-by-step.\n\n" + prompt,
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="Markdown"
        )
        return States.GETTING_NAME
    else:  # "👍 No, looks good"
        # Clear the review_mode flag if it was set
        if 'review_mode' in context.user_data:
            del context.user_data['review_mode']
            
        reply_keyboard = [["✅ Yes, please!", "❌ No, thanks"]]
        await update.message.reply_text(
            "Great! Would you like me to tailor your resume for a specific job description?",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
        )
        return States.ASKING_TAILOR


async def handle_tailor_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's choice about tailoring."""
    choice = update.message.text

    if "✅ Yes, please!" in choice:
        await update.message.reply_text("Great! Please paste the job description below.", reply_markup=ReplyKeyboardRemove())
        return States.GETTING_JOB_DESCRIPTION
    else:
        await update.message.reply_text("Okay, I'll generate your resume with the information I have.", reply_markup=ReplyKeyboardRemove())
        return await generate_and_send_pdf(update, context)


async def get_job_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gets the job description and calls the tailoring AI."""
    job_description = update.message.text
    await update.message.reply_text("Analyzing the job description and tailoring your resume...")

    tailoring_suggestions = gemini_client.tailor_resume_for_job(context.user_data, job_description)

    if tailoring_suggestions:
        context.user_data["tailored_summary"] = tailoring_suggestions["tailored_summary"]
        
        reply_keyboard = [["✅ Apply Changes", "❌ Keep Original"]]

        skills_text = "\n- ".join(tailoring_suggestions["suggested_skills"])
        await update.message.reply_text(
            "Here are my suggestions:\n\n"
            "**Tailored Summary:**\n"
            f"_{tailoring_suggestions['tailored_summary']}_\n\n"
            "**Suggested Skills to Add:**\n"
            f"- {skills_text}\n\n"
            "Would you like to apply the new summary to your resume?",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="Markdown"
        )
        return States.AWAITING_TAILOR_APPROVAL
    else:
        await update.message.reply_text("Sorry, the AI tailoring failed. I'll generate the resume with your original data.")
        return await generate_and_send_pdf(update, context)


async def handle_tailor_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's choice for the tailoring and generates the PDF."""
    choice = update.message.text

    if "✅ Apply Changes" in choice:
        context.user_data["summary"] = context.user_data["tailored_summary"]
        await update.message.reply_text("Okay, I've updated your summary.", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text("No problem. I'll use your original summary.", reply_markup=ReplyKeyboardRemove())
    
    return await generate_and_send_pdf(update, context)


async def generate_and_send_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE, exclude_template: str = None) -> int:
    """Helper function to generate, send, and clean up the PDF."""
    message_sender = update.callback_query.message if update.callback_query else update.message
    await message_sender.reply_text("I'm now generating your resume...")

    logger.info(f"Final user data: {context.user_data}")
    
    # The generator now returns a tuple: (path, template_name)
    pdf_generation_result = generator.generate_pdf(context.user_data, exclude_template=exclude_template)

    if pdf_generation_result:
        pdf_path, template_name = pdf_generation_result
        context.user_data['last_template'] = template_name # Save the used template
        
        # Initialize or increment the regeneration counter
        if 'regeneration_count' not in context.user_data:
            context.user_data['regeneration_count'] = 1
        
        await message_sender.reply_document(
            document=open(pdf_path, 'rb'),
            filename=f"{context.user_data.get('name', 'resume')}.pdf",
            caption="Here is your generated resume!"
        )
        os.remove(pdf_path)

        reply_keyboard = [["🎨 Regenerate with New Design", "✅ Finish"]]
        await message_sender.reply_text(
            "What would you like to do next?",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
        )
        return States.AWAITING_REGENERATION

    else:
        await message_sender.reply_text("Sorry, something went wrong while generating your PDF.")
        # Clean up and end conversation on failure
        return await finish_conversation(update, context)


async def handle_regeneration_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's choice to regenerate or finish."""
    choice = update.message.text

    if "🎨 Regenerate with New Design" in choice:
        if context.user_data['regeneration_count'] >= 5:
            await update.message.reply_text(
                "You have reached the maximum number of regenerations for this session. Please start over to create a new resume.",
                reply_markup=ReplyKeyboardRemove()
            )
            return await finish_conversation(update, context)
        
        context.user_data['regeneration_count'] += 1
        await update.message.reply_text("On it! Generating a new design...", reply_markup=ReplyKeyboardRemove())
        # Call the generator again, excluding the last template used
        return await generate_and_send_pdf(update, context, exclude_template=context.user_data.get('last_template'))
    else:  # "✅ Finish"
        return await finish_conversation(update, context)


async def finish_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Clears user data and ends the conversation."""
    await update.message.reply_text("Great! Feel free to start over any time with /start.", reply_markup=ReplyKeyboardRemove())
    
    if context.user_data.get('photo_path'):
        local_photo_path = context.user_data['photo_path'].replace('file://', '')
        if os.path.exists(local_photo_path):
            try:
                os.remove(local_photo_path)
                logger.info(f"Cleaned up photo: {local_photo_path}")
            except OSError as e:
                logger.error(f"Error cleaning up photo {local_photo_path}: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text("Operation cancelled.", reply_markup=ReplyKeyboardRemove())
    
    # Perform the same cleanup as finish_conversation
    if context.user_data.get('photo_path'):
        local_photo_path = context.user_data['photo_path'].replace('file://', '')
        if os.path.exists(local_photo_path):
            try:
                os.remove(local_photo_path)
                logger.info(f"Cleaned up photo: {local_photo_path}")
            except OSError as e:
                logger.error(f"Error cleaning up photo {local_photo_path}: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def invalid_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles any input that is not appropriate for the current state."""
    await update.message.reply_text(
        "Sorry, I was expecting different input. Please follow the instructions or type /cancel to start over."
    )
    # This does not change the state
    return


async def fallback_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catches any button clicks that don't match a state."""
    query = update.callback_query
    await query.answer()
    logger.warning(f"Fallback callback handler triggered for data: {query.data}")
    await query.edit_message_text(
        "Something went wrong! This button is not active. Please type /start to begin again."
    )
    return ConversationHandler.END


async def start_smart_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the smart resume process."""
    await update.message.reply_text(
        "Welcome to the Smart Resume feature!\n\n"
        "Please paste your entire resume content below in a single message. "
        "I will do my best to extract all the relevant information automatically.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return States.GETTING_SMART_INPUT


async def get_all_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the user's single text block and uses Gemini to parse it."""
    user_text = update.message.text
    await update.message.reply_text("Thank you. I am now processing your information with AI. This may take a moment...")

    parsed_data = gemini_client.parse_resume_data(user_text)

    if not parsed_data:
        await update.message.reply_text(
            "I'm sorry, I couldn't extract the information from your text. "
            "Let's try the manual step-by-step process instead."
        )
        return await start(update, context) # Fallback to the standard start

    # Store the parsed data in user_data
    context.user_data.update(parsed_data)

    # Ensure essential keys have default values if missing
    context.user_data.setdefault('skills', [])
    context.user_data.setdefault('experience', [])
    context.user_data.setdefault('education', [])

    # A random template will be chosen, so we only set the default color and photo path
    context.user_data.setdefault('accent_color', '#3498db')
    context.user_data.setdefault('photo_path', None)

    # Create a confirmation message
    confirmation_message = (
        "I have extracted the following information:\n\n"
        f"**Name:** {parsed_data.get('name', 'Not found')}\n"
        f"**Email:** {parsed_data.get('email', 'Not found')}\n"
        f"**Phone:** {parsed_data.get('phone', 'Not found')}\n"
        f"**Summary:** {parsed_data.get('summary', 'Not found')}\n"
        f"**Skills:** {len(parsed_data.get('skills', []))} found\n"
        f"**Experience:** {len(parsed_data.get('experience', []))} entries found\n\n"
        "Does this look correct?"
    )

    reply_keyboard = [["✅ Looks Good!", "✍️ Edit Manually"]]

    await update.message.reply_text(
        confirmation_message,
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
        parse_mode="Markdown"
    )

    return States.AWAITING_SMART_APPROVAL


async def handle_smart_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's confirmation of the parsed data."""
    choice = update.message.text

    if "✅ Looks Good!" in choice:
        await update.message.reply_text("Great! All your information has been saved.", reply_markup=ReplyKeyboardRemove())
        # All data is collected, so we can now ask about tailoring
        return await education_done(update, context)
    else:  # "✍️ Edit Manually"
        context.user_data['review_mode'] = True
        name = context.user_data.get('name')
        prompt = f"I found the name: `{name}`.\nPlease send the correct name, or send this one to confirm." if name else "What is your full name?"

        await update.message.reply_text(
            "No problem. Let's review the extracted information step-by-step.\n\n" + prompt,
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="Markdown"
        )
        return States.GETTING_NAME


async def main() -> None:
    """Run the bot with a webhook."""
    application = Application.builder().token(config.TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            States.SELECTING_COLOR: [
                MessageHandler(filters.Regex("^(?i)(blue|green|red|purple)$"), select_color),
            ],
            States.AWAITING_PHOTO_CHOICE: [
                MessageHandler(filters.Regex("^(📷 Upload Photo|➡️ Skip Photo)$"), handle_photo_choice)
            ],
            States.CHOOSING_INPUT_METHOD: [
                MessageHandler(filters.Regex("^(📝 Step-by-step|🤖 Smart Paste \(AI\))$"), handle_input_method_choice)
            ],
            States.UPLOADING_PHOTO: [
                MessageHandler(filters.PHOTO, handle_photo)
            ],
            States.GETTING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)
            ],
            States.GETTING_CONTACTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_contacts)
            ],
            States.GETTING_SUMMARY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_summary)
            ],
            States.AWAITING_SUMMARY_APPROVAL: [
                MessageHandler(filters.Regex("^(✅ Use AI Version|✍️ Keep My Version)$"), handle_summary_approval)
            ],
            States.GETTING_SKILLS: [
                MessageHandler(filters.Regex("^Done$"), skills_done),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_skill),
            ],
            States.GETTING_EXPERIENCE: [
                MessageHandler(filters.Regex("^Done$"), experience_done),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_experience),
            ],
            States.GETTING_EDUCATION: [
                MessageHandler(filters.Regex("^Done$"), education_done),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_education),
            ],
            States.ASK_FOR_REVIEW: [
                MessageHandler(filters.Regex("^(✍️ Yes, review my data|👍 No, looks good)$"), handle_review_choice)
            ],
            States.ASKING_TAILOR: [
                MessageHandler(filters.Regex("^(✅ Yes, please!|❌ No, thanks)$"), handle_tailor_choice)
            ],
            States.GETTING_JOB_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_job_description)
            ],
            States.AWAITING_TAILOR_APPROVAL: [
                MessageHandler(filters.Regex("^(✅ Apply Changes|❌ Keep Original)$"), handle_tailor_approval)
            ],
            States.GETTING_SMART_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_all_data)
            ],
            States.AWAITING_SMART_APPROVAL: [
                MessageHandler(filters.Regex("^(✅ Looks Good!|✍️ Edit Manually)$"), handle_smart_approval)
            ],
            States.AWAITING_REGENERATION: [
                MessageHandler(filters.Regex("^(🎨 Regenerate with New Design|✅ Finish)$"), handle_regeneration_choice)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, invalid_input),
        ],
    )

    application.add_handler(conv_handler)

    logger.info("Starting bot with webhook...")

    # Get webhook URL and port from environment variables.
    # The WEBHOOK_URL is the base URL of the web server, e.g., https://your-app-name.on-render.com
    webhook_url = os.environ.get("WEBHOOK_URL")
    if not webhook_url:
        logger.error("WEBHOOK_URL environment variable not set!")
        return

    # The port must be specified by the hosting service.
    port = int(os.environ.get("PORT", 8443))

    # We use the bot token as the url path, which is a common practice.
    # The full webhook URL will be https://your-app-name.on-render.com/<TELEGRAM_TOKEN>
    # We also use it as a secret token for an extra layer of security.
    await application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=config.TELEGRAM_TOKEN,
        webhook_url=webhook_url,
        secret_token=config.TELEGRAM_TOKEN,
    )


if __name__ == "__main__":
    asyncio.run(main())
