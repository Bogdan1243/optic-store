import os
import sys
import django
import io
from PIL import Image

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from store.models import Product, ProductImage
from django.core.files import File

def get_compressed_file(file_path):
    """
    Compresses an image to stay well below Cloudinary's 10MB limit.
    Resizes max dimensions to 2000px.
    Preserves transparency by saving as PNG, otherwise saves as optimized JPEG.
    """
    img = Image.open(file_path)
    
    # Check if the image has a transparency channel
    has_alpha = img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info)
    
    # Resize if dimensions are huge
    max_size = 2000
    if img.width > max_size or img.height > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
    output = io.BytesIO()
    base_name = os.path.basename(file_path)
    name_without_ext = os.path.splitext(base_name)[0]
    
    if has_alpha:
        # Save as PNG to preserve the transparent background!
        if img.mode == 'P':
            img = img.convert('RGBA')
        img.save(output, format='PNG', optimize=True)
        new_name = name_without_ext + ".png"
    else:
        # Convert to RGB and save as JPEG to save space
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(output, format='JPEG', quality=85, optimize=True)
        new_name = name_without_ext + ".jpg"
        
    output.seek(0)
    return new_name, output

def batch_upload():
    print("=== Optic Store Image Batch Uploader ===")
    folder_path = input("Enter the absolute path to your folder with pictures: ").strip()
    
    if not os.path.exists(folder_path):
        print("Folder does not exist!")
        return
        
    skip_existing = input("Skip products that already have images? (y/n, default y): ").strip().lower() != 'n'
    
    specific_models_input = input("Enter specific model codes to force-update (comma separated), or leave blank for all: ").strip()
    specific_models = [m.strip().lower() for m in specific_models_input.split(',')] if specific_models_input else []

    allowed_angles = ['qt', 'lt', 'fr', 'cfr', 'bk']
    
    # groups[model_code][color_code][angle] = filepath
    groups = {}
    found_count = 0

    print("Scanning folder for valid images...")
    for root, _, files in os.walk(folder_path):
        for file in files:
            file_lower = file.lower()
            
            # Must be an image
            if not file_lower.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                continue
                
            # MUST have 'shad' and NOT 'noshad'
            if 'shad' not in file_lower or 'noshad' in file_lower:
                continue
                
            # Parse filename: e.g. 0RB4179__601S9A__STD__shad__qt.jpg
            name, ext = os.path.splitext(file)
            parts = name.split('__')
            
            if len(parts) < 3:
                continue
                
            model_code = parts[0]
            
            # If you provided specific models, ignore all others!
            if specific_models and model_code.lower() not in specific_models:
                continue
                
            color_code = parts[1]
            angle = parts[-1].lower()
            
            if angle not in allowed_angles:
                continue
                
            if model_code not in groups:
                groups[model_code] = {}
            if color_code not in groups[model_code]:
                groups[model_code][color_code] = {}
                
            groups[model_code][color_code][angle] = os.path.join(root, file)
            found_count += 1

    print(f"Found {found_count} matching pictures across {len(groups)} unique product models.")
    if found_count == 0:
        print("No pictures matched your criteria.")
        return

    print("\nStarting matching and upload process...")
    
    for model_code, colors in groups.items():
        # Find product in DB
        db_products = list(Product.objects.filter(model_code__iexact=model_code).order_by('id'))
        
        if not db_products:
            print(f"\n⚠️ Skipping {model_code}: Could not find this model code in the database.")
            continue
            
        for color_code, images in colors.items():
            target_product = None
            
            # Filter products to only those without an image if skip_existing is True
            # (Unless we specifically requested this model, then we want to overwrite it!)
            if skip_existing and not specific_models:
                available_products = [p for p in db_products if not p.image]
            else:
                available_products = db_products
                
            if not available_products:
                print(f"\n⏭️ Skipping {model_code} (Color code {color_code}) - already has images uploaded.")
                continue
            
            if len(available_products) == 1:
                target_product = available_products[0]
                print(f"\n✅ Auto-matched {model_code} (Color code {color_code}) to '{target_product.color}'")
            else:
                print(f"\n==============================================")
                print(f"📸 Found pictures for {model_code} (Color code: {color_code})")
                print(f"Which of your database products is this? (Products that already have images are hidden)")
                for i, p in enumerate(available_products):
                    print(f"  {i+1}. {p.color} (ID: {p.id})")
                
                while True:
                    choice = input(f"Type 1-{len(available_products)} to select, or 's' to skip: ").strip()
                    if choice.lower() == 's':
                        break
                    if choice.isdigit() and 1 <= int(choice) <= len(available_products):
                        target_product = available_products[int(choice)-1]
                        break
                    print("Invalid choice. Try again.")
            
            if target_product:
                # Decide which image is the main one. Prioritize 'qt' (quarter turn)
                main_angle = 'qt' if 'qt' in images else ('fr' if 'fr' in images else list(images.keys())[0])
                main_img_path = images.pop(main_angle)
                
                print(f"  -> Compressing and Uploading MAIN image ({main_angle}) to Cloudinary...")
                new_name, compressed_file = get_compressed_file(main_img_path)
                target_product.image.save(new_name, File(compressed_file), save=True)
                
                # Upload the rest to the gallery
                # Clear existing gallery images to prevent duplicates if re-running!
                target_product.images.all().delete()
                
                for ang, path in images.items():
                    print(f"  -> Compressing and Uploading GALLERY image ({ang})...")
                    new_name, compressed_file = get_compressed_file(path)
                    pi = ProductImage(product=target_product)
                    pi.image.save(new_name, File(compressed_file), save=True)
                
                print(f"  Done uploading {len(images) + 1} pictures for {model_code} - {target_product.color}.")

    print("\n🎉 All finished!")

if __name__ == '__main__':
    batch_upload()
