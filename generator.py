import os
import uuid
import logging
import random
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

import gemini_client
from config import TEMPLATES

async def generate_pdf(user_data: dict, selected_template: str = None, exclude_template: str = None) -> tuple[str, str] | None:
    """
    Generates a PDF resume from user data and a template.

    Args:
        user_data: A dictionary containing all the user's information.
        selected_template: The name of a specific template to use.
        exclude_template: The name of a template to exclude from random selection.

    Returns:
        A tuple containing the file path of the generated PDF and the template name used,
        or None if an error occurs.
    """
    try:
        # Get the absolute path of the directory containing this script (resume_bot/)
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # The templates directory is a subdirectory of the script's directory
        templates_dir = os.path.join(script_dir, 'templates')

        # 1. Set up Jinja2 environment with a reliable path to the templates directory
        env = Environment(loader=FileSystemLoader(templates_dir))

        # 2. Select a template
        if selected_template and selected_template in TEMPLATES:
            template_name = selected_template
        else:
            available_templates = list(TEMPLATES.keys())
            if exclude_template and exclude_template in available_templates:
                available_templates.remove(exclude_template)

            if not available_templates:
                # Fallback if all templates were excluded (e.g., only one exists)
                available_templates = list(TEMPLATES.keys())

            template_name = random.choice(available_templates)
        template_path = TEMPLATES[template_name]
        logging.info(f"Randomly selected template: {template_name}")

        # The loader's search path is now the templates dir, so we just need the filename
        template_filename = os.path.basename(template_path)
        template = env.get_template(template_filename)

        # 3. Generate 'About Me' text and render the HTML template with user data
        about_me_text = await gemini_client.generate_about_me(user_data)
        if about_me_text:
            user_data['about_me'] = about_me_text

        # Remove summary from user_data if it exists
        if 'summary' in user_data:
            del user_data['summary']

        # Ensure photo_path is a file URI for local access, which is required by WeasyPrint
        if 'photo_path' in user_data and user_data.get('photo_path') and os.path.exists(user_data['photo_path']):
            user_data['photo_path'] = Path(os.path.abspath(user_data['photo_path'])).as_uri()

        html_out = template.render(user_data)

        # 4. Create a temporary output file path
        output_dir = "/tmp/resume_bot/pdfs"
        os.makedirs(output_dir, exist_ok=True)
        pdf_path = os.path.join(output_dir, f"resume_{uuid.uuid4()}.pdf")

        # 5. Call WeasyPrint to convert HTML to PDF
        # The base_url should be the templates directory to resolve any relative asset paths
        HTML(string=html_out, base_url=templates_dir).write_pdf(pdf_path)

        return pdf_path, template_name

    except Exception as e:
        logging.error(f"Error generating PDF: {e}")
        return None
