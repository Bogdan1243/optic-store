import os
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

load_dotenv()

cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
api_key = os.getenv('CLOUDINARY_API_KEY')
api_secret = os.getenv('CLOUDINARY_API_SECRET')

if not all([cloud_name, api_key, api_secret]):
    raise ValueError("Missing Cloudinary credentials! Check your .env file.")

cloudinary.config(
    cloud_name=cloud_name,
    api_key=api_key,
    api_secret=api_secret,
    secure=True
)

media_dir = 'media'
ALLOWED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg')

for root, _, files in os.walk(media_dir):
    for file in files:
        if file.startswith('.'):
            continue

        if file.lower().endswith(ALLOWED_EXTENSIONS):
            local_path = os.path.join(root, file)
            clean_path = local_path.replace('\\', '/')

            # STRIP the extension for the public_id (e.g., media/products/.../image)
            public_id, ext = os.path.splitext(clean_path)

            # Extract just the letters of the extension (e.g., 'png')
            ext = ext.lstrip('.')

            print(f"Uploading ID: {public_id} | Format: {ext}")

            cloudinary.uploader.upload(
                local_path,
                public_id=public_id,  # NO extension here!
                format=ext,  # Passed separately here!
                overwrite=True,
                invalidate=True
            )

print("All media uploaded perfectly!")