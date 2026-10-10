from django import forms
from django.contrib import admin, messages
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import path
from .models import Product, ProductImage, Order, OrderItem, Review
from .excel_import import import_products_from_excel, generate_sample_xlsx


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={'multiple': True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(d, initial) for d in data]
        return single_file_clean(data, initial)

class ProductAdminForm(forms.ModelForm):
    batch_images = MultipleFileField(
        required=False,
        label="Încărcare batch poze",
        help_text="Selectează mai multe imagini simultan din Finder (folosind Cmd + Click sau Shift + Click)."
    )

    class Meta:
        model = Product
        fields = '__all__'


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = ('brand', 'model_code', 'slug', 'category', 'color', 'color_hex', 'size', 'price', 'sex', 'created_at')
    list_filter = ('category', 'sex', 'progressive_friendly', 'frame_shape')
    search_fields = ('brand', 'model_code', 'slug', 'color', 'description')
    readonly_fields = ('slug',)
    inlines = [ProductImageInline]

    fieldsets = (
        ('Informații de Bază', {
            'fields': ('brand', 'model_code', 'slug', 'price', 'category', 'sex', 'color', 'color_hex', 'size', 'description', 'image', 'ar_image', 'batch_images')
        }),
        ('Specificații Cadru', {
            'fields': ('frame_shape', 'frame_material', 'frame_finish', 'rim_type', 'bridge_length', 'temple_length', 'hinge_to_hinge')
        }),
        ('Specificații Lentilă', {
            'fields': ('lens_color', 'lens_width', 'lens_height', 'lens_base')
        }),
        ('Potrivire & Rețetă', {
            'fields': ('face_shape', 'age_group', 'progressive_friendly')
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-excel/', self.admin_site.admin_view(self.import_excel_view), name='product-import-excel'),
            path('download-template/', self.admin_site.admin_view(self.download_template_view), name='product-download-template'),
        ]
        return custom_urls + urls

    def import_excel_view(self, request):
        if request.method == 'POST':
            excel_file = request.FILES.get('excel_file')
            zip_file = request.FILES.get('zip_file')

            if not excel_file:
                messages.error(request, "Te rugăm să selectezi un fișier Excel (.xlsx).")
                return HttpResponseRedirect(request.path)

            res = import_products_from_excel(excel_file, zip_file_or_path=zip_file)

            if res['errors']:
                for err in res['errors']:
                    messages.error(request, f"Eroare: {err}")
            else:
                msg = f"Import finalizat cu succes! Produse create: {res['created']}, actualizate: {res['updated']}."
                messages.success(request, msg)

                if res['warnings']:
                    for warn in res['warnings']:
                        messages.warning(request, f"Atenție: {warn}")

                return HttpResponseRedirect('../')

        context = {
            **self.admin_site.each_context(request),
            'title': 'Import Produse din Excel (XLSX)',
            'opts': self.model._meta,
        }
        return render(request, 'admin/store/product/excel_import.html', context)

    def download_template_view(self, request):
        content = generate_sample_xlsx()
        response = HttpResponse(
            content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="product_import_template.xlsx"'
        return response

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        images = request.FILES.getlist('batch_images')
        for img in images:
            ProductImage.objects.create(product=form.instance, image=img)


admin.site.register(Product, ProductAdmin)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(Review)