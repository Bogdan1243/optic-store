import io
import zipfile
import openpyxl
from django.test import TestCase, override_settings
from store.models import Product, ProductImage
from store.excel_import import import_products_from_excel, generate_sample_xlsx


@override_settings(DEFAULT_FILE_STORAGE='django.core.files.storage.FileSystemStorage')
class ExcelImportTestCase(TestCase):

    def test_generate_sample_xlsx(self):
        content = generate_sample_xlsx()
        self.assertTrue(len(content) > 0)
        wb = openpyxl.load_workbook(io.BytesIO(content))
        ws = wb.active
        headers = [cell.value for cell in ws[1]]
        self.assertIn('brand', headers)
        self.assertIn('price', headers)
        self.assertIn('color', headers)
        self.assertIn('size', headers)

    def test_import_products_without_images(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['brand', 'model_code', 'color', 'size', 'price', 'category', 'sex', 'description'])
        ws.append(['Gucci', 'GG0001', 'Gold', '54-18', 299.99, 'SUN', 'Women', 'Luxury sunglasses'])

        excel_io = io.BytesIO()
        wb.save(excel_io)
        excel_io.seek(0)

        res = import_products_from_excel(excel_io)
        self.assertEqual(res['created'], 1)
        self.assertEqual(res['updated'], 0)
        self.assertEqual(len(res['errors']), 0)

        product = Product.objects.get(brand='Gucci', color='Gold')
        self.assertEqual(float(product.price), 299.99)
        self.assertEqual(product.model_code, 'GG0001')
        self.assertEqual(product.sex, 'Women')

    def test_import_products_with_zip_images(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['brand', 'color', 'size', 'price', 'image', 'ar_image', 'gallery_images'])
        ws.append(['Prada', 'Black', '52-20', 350.00, 'prada_front.jpg', 'prada_ar.png', 'prada_side.jpg'])

        excel_io = io.BytesIO()
        wb.save(excel_io)
        excel_io.seek(0)

        zip_io = io.BytesIO()
        with zipfile.ZipFile(zip_io, 'w') as zf:
            zf.writestr('prada_front.jpg', b'fake_jpg_data')
            zf.writestr('prada_ar.png', b'fake_png_data')
            zf.writestr('prada_side.jpg', b'fake_side_data')
        zip_io.seek(0)

        res = import_products_from_excel(excel_io, zip_file_or_path=zip_io)
        self.assertEqual(res['created'], 1)

        product = Product.objects.get(brand='Prada', color='Black')
        self.assertTrue(bool(product.image))
        self.assertTrue(bool(product.ar_image))

        gallery_count = ProductImage.objects.filter(product=product).count()
        self.assertEqual(gallery_count, 1)

    def test_import_updates_existing_product(self):
        Product.objects.create(
            brand='Tom Ford',
            color='Havana',
            size='51-19',
            price=200.00,
            category='SUN'
        )

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['brand', 'color', 'size', 'price', 'category'])
        ws.append(['Tom Ford', 'Havana', '51-19', 249.99, 'SUN'])

        excel_io = io.BytesIO()
        wb.save(excel_io)
        excel_io.seek(0)

        res = import_products_from_excel(excel_io)
        self.assertEqual(res['created'], 0)
        self.assertEqual(res['updated'], 1)

        product = Product.objects.get(brand='Tom Ford', color='Havana')
        self.assertEqual(float(product.price), 249.99)
