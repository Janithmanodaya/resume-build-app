from PIL import Image, ImageDraw, ImageFont
import os

def add_text_to_image(image_path: str, text: str, output_path: str):
    """
    Adds a text overlay to an image and saves it to a new path.
    """
    try:
        img = Image.open(image_path)
        draw = ImageDraw.Draw(img)

        # Try to load a font, fall back to default
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except IOError:
            font = ImageFont.load_default()

        # Position the text on the top-left corner
        text_position = (20, 20)

        # Add a semi-transparent background for the text for better readability
        text_bbox = draw.textbbox(text_position, text, font=font)
        bg_rect = (text_bbox[0] - 10, text_bbox[1] - 10, text_bbox[2] + 10, text_bbox[3] + 10)
        draw.rectangle(bg_rect, fill=(0, 0, 0, 128))

        # Draw the text
        draw.text(text_position, text, font=font, fill=(255, 255, 255))

        # Ensure the output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        img.save(output_path)
        return True

    except Exception as e:
        print(f"Error adding text to image: {e}")
        return False
