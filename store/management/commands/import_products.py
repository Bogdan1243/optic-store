import os
from django.core.management.base import BaseCommand, CommandError
from store.excel_import import import_products_from_excel, generate_sample_xlsx


class Command(BaseCommand):
    help = 'Import products from an Excel (.xlsx) file with optional image ZIP archive or directory.'

    def add_arguments(self, parser):
        parser.add_argument('excel_file', nargs='?', type=str, help='Path to the .xlsx file to import.')
        parser.add_argument('--zip', type=str, help='Path to a .zip archive containing product images.')
        parser.add_argument('--image-dir', type=str, help='Path to a directory containing product images.')
        parser.add_argument('--generate-template', type=str, help='Path to save a sample Excel import template (e.g., template.xlsx).')

    def handle(self, *args, **options):
        template_path = options.get('generate_template')
        if template_path:
            content = generate_sample_xlsx()
            with open(template_path, 'wb') as f:
                f.write(content)
            self.stdout.write(self.style.SUCCESS(f"Sample template generated at: {template_path}"))
            return

        excel_file = options.get('excel_file')
        if not excel_file:
            raise CommandError("Please provide an excel_file path or use --generate-template <path>.")

        if not os.path.exists(excel_file):
            raise CommandError(f"Excel file not found at: {excel_file}")

        zip_file = options.get('zip')
        if zip_file and not os.path.exists(zip_file):
            raise CommandError(f"ZIP file not found at: {zip_file}")

        image_dir = options.get('image_dir')
        if image_dir and not os.path.exists(image_dir):
            raise CommandError(f"Image directory not found at: {image_dir}")

        self.stdout.write(f"Importing products from '{excel_file}'...")
        res = import_products_from_excel(excel_file, zip_file_or_path=zip_file, image_dir=image_dir)

        if res['errors']:
            for err in res['errors']:
                self.stdout.write(self.style.ERROR(f"Error: {err}"))

        if res['warnings']:
            for warn in res['warnings']:
                self.stdout.write(self.style.WARNING(f"Warning: {warn}"))

        self.stdout.write(
            self.style.SUCCESS(f"Import finished! Products created: {res['created']}, updated: {res['updated']}.")
        )
