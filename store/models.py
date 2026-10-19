from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.urls import reverse
from datetime import timedelta
import datetime
from django.contrib.auth.models import User


class Product(models.Model):
    slug = models.SlugField(max_length=200, unique=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    @property
    def is_new(self):
        return self.created_at >= timezone.now()- timedelta(days=1)
    brand = models.CharField(max_length=100)
    model_code = models.CharField(max_length=50, blank=True, null=True, db_index=True, verbose_name="Cod Model (ex: RB2140)")
    color = models.CharField(max_length=50)
    color_hex = models.CharField(max_length=30, blank=True, null=True, verbose_name="Cod Culoare / Hex (ex: #000000 sau #8B4513)")
    size = models.CharField(max_length=20)
    price= models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='products/%Y/%m/%d')
    ar_image = models.ImageField(upload_to='uploads/ar_images/', blank=True, null=True,
                                 help_text="Upload a transparent PNG of the glasses front-view.")
    description = models.TextField(blank = True, null = True)

    @property
    def get_image_url(self):
        if self.image:
            try:
                return self.image.url
            except ValueError:
                pass
        first_img = self.images.first() if hasattr(self, 'images') else None
        if first_img and first_img.image:
            try:
                return first_img.image.url
            except ValueError:
                pass
        return ''


    CATEGORY_CHOICES = [
        ('SUN', 'Sunglasses'),
        ('OPT', 'Optical')
    ]
    SEX_CHOICES = (
        ('Men', 'Men'),
        ('Women', 'Women'),
        ('Children', 'Children'),
        ('Unisex', 'Unisex'),
    )
    category = models.CharField(max_length = 50, choices = CATEGORY_CHOICES, default = 'SUN')
    sex = models.CharField(max_length = 50, choices = SEX_CHOICES, default = 'Unisex')

    # --- DETALII PRODUS (SPECIFICAȚII) ---
    # Cadru
    frame_shape = models.CharField(max_length=50, blank=True, null=True, verbose_name="Formă cadru")
    frame_material = models.CharField(max_length=50, blank=True, null=True, verbose_name="Material cadru/față")
    frame_finish = models.CharField(max_length=50, blank=True, null=True, verbose_name="Finisaj")
    rim_type = models.CharField(max_length=50, blank=True, null=True, verbose_name="Tip margine")
    bridge_length = models.CharField(max_length=20, blank=True, null=True, verbose_name="Lungime punte")
    temple_length = models.CharField(max_length=20, blank=True, null=True, verbose_name="Lungime brațe")
    hinge_to_hinge = models.CharField(max_length=50, blank=True, null=True, verbose_name="Balama-la-balama")

    # Lentilă
    lens_color = models.CharField(max_length=50, blank=True, null=True, verbose_name="Culoare lentile")
    lens_width = models.CharField(max_length=20, blank=True, null=True, verbose_name="Lățime lentilă")
    lens_height = models.CharField(max_length=20, blank=True, null=True, verbose_name="Înălțime lentilă")
    lens_base = models.CharField(max_length=50, blank=True, null=True, verbose_name="Bază lentilă")

    # General
    face_shape = models.CharField(max_length=50, blank=True, null=True, verbose_name="Forma feței")
    progressive_friendly = models.BooleanField(default=False, verbose_name="Progressive friendly / Rețetă")
    age_group = models.CharField(max_length=50, blank=True, null=True, verbose_name="Grup de vârstă")

    def __str__(self):
        return f"{self.brand} - {self.color} ({self.get_category_display()})"

    def _generate_slug(self):
        """Generate a URL-friendly slug from model_code + color.
        Examples: '0VO5239' + 'Negru' → 'vo5239-negru'
                  '0RB2132' + 'Negru Mat' → 'rb2132-negru-mat'
        Falls back to brand + color for products without model_code.
        """
        if self.model_code:
            # Strip leading '0' from codes like '0VO5239' → 'VO5239'
            code = self.model_code.lstrip('0')
        else:
            code = self.brand

        base_slug = slugify(f"{code}-{self.color}")
        if not base_slug:
            base_slug = slugify(f"{self.brand}-{self.pk or 'new'}")

        # Ensure uniqueness
        slug = base_slug
        counter = 2
        while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    def save(self, *args, **kwargs):
        if not self.slug:
            # Need pk for uniqueness check on first save
            if not self.pk:
                super().save(*args, **kwargs)
                args = ()
                kwargs.pop('force_insert', None)
            self.slug = self._generate_slug()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('product_detail', kwargs={'slug': self.slug})

    @property
    def has_specs(self):
        return any([
            self.frame_shape, self.frame_material, self.frame_finish, self.rim_type,
            self.bridge_length, self.temple_length, self.hinge_to_hinge, self.lens_color, self.lens_width,
            self.lens_height, self.lens_base, self.face_shape, self.progressive_friendly,
            self.age_group
        ])

    def get_all_variants(self):
        """Returns all products in the same model_code group, including self."""
        if self.model_code:
            return Product.objects.filter(model_code=self.model_code).order_by('id')
        return Product.objects.filter(id=self.id)

    def get_other_variants(self):
        """Returns all other products in the same model_code group, excluding self."""
        if self.model_code:
            return Product.objects.filter(model_code=self.model_code).exclude(id=self.id).order_by('id')
        return Product.objects.none()

    @property
    def size_list(self):
        """Returns a list of individual sizes parsed from the size field (e.g. 'S, M' -> ['S', 'M'])."""
        if not self.size:
            return []
        return [s.strip() for s in str(self.size).split(',') if s.strip()]


    @property
    def get_color_hex_default(self):
        """Fallback color hex helper for standard color names if color_hex is not set."""
        if self.color_hex:
            return self.color_hex
        color_map = {
            'black': '#111111',
            'negru': '#111111',
            'gold': '#D4AF37',
            'auriu': '#D4AF37',
            'auresiu': '#D4AF37',
            'silver': '#C0C0C0',
            'argintiu': '#C0C0C0',
            'tortoise': '#543D2B',
            'brown': '#654321',
            'maro': '#654321',
            'beige': '#F5F5DC',
            'bej': '#D2B48C',
            'blue': '#1E3A8A',
            'albastru': '#1E3A8A',
            'red': '#B91C1C',
            'rosu': '#B91C1C',
            'green': '#047857',
            'verde': '#047857',
            'pink': '#EC4899',
            'roz': '#EC4899',
            'transparent': 'rgba(220,220,220,0.5)',
        }
        cleaned = (self.color or '').lower().strip()
        for key, val in color_map.items():
            if key in cleaned:
                return val
        return '#777777'

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/gallery/%Y/%m/%d')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Gallery Image ({self.id}) for {self.product.brand}"

class Order(models.Model):
    # Link to a user, but allow it to be empty (null=True) for Guest Checkout
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    full_name = models.CharField(max_length=250)
    email = models.EmailField(max_length=250)
    shipping_address = models.TextField(max_length=15000)

    # Financials
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    date_ordered = models.DateTimeField(auto_now_add=True)

    # Logistics
    shipped = models.BooleanField(default=False)
    date_shipped = models.DateTimeField(blank=True, null=True)

    paid = models.BooleanField(default=False)

    def __str__(self):
        return f'Order - {str(self.id)}'


# 2. The Items (What they bought)
class OrderItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    # 👇 ADD THESE PRESCRIPTION FIELDS 👇
    od_sph = models.CharField(max_length=10, blank=True, null=True)
    od_cyl = models.CharField(max_length=10, blank=True, null=True)
    od_axis = models.CharField(max_length=10, blank=True, null=True)
    os_sph = models.CharField(max_length=10, blank=True, null=True)
    os_cyl = models.CharField(max_length=10, blank=True, null=True)
    os_axis = models.CharField(max_length=10, blank=True, null=True)
    pd = models.CharField(max_length=10, blank=True, null=True)

    def __str__(self):
        return f"{self.quantity} x {self.product.brand}"
class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(default=5) # 1 to 5 stars
    comment = models.TextField(max_length=500, blank=True)
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} on {self.product.brand}"


class ReturnRequest(models.Model):
    REASON_CHOICES = [
        ('nepotrivire', 'Nu mi se potrivesc / Decizie personală (fără motiv)'),
        ('defect', 'Produs cu defect de fabricație'),
        ('gresit', 'Produs greșit / Nu corespunde specificațiilor din comandă'),
        ('altul', 'Alt motiv'),
    ]

    REFUND_METHOD_CHOICES = [
        ('card', 'Restituire automată pe cardul utilizat la plata comenzii inițiale'),
        ('iban', 'Transfer bancar în contul IBAN'),
    ]

    STATUS_CHOICES = [
        ('pending', 'În așteptare'),
        ('approved', 'Aprobat'),
        ('rejected', 'Respins'),
        ('refunded', 'Rambursat'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    order_number = models.CharField(max_length=100, verbose_name="Număr Comandă")
    full_name = models.CharField(max_length=250, verbose_name="Nume și Prenume")
    email = models.EmailField(max_length=250, verbose_name="Adresă de E-mail")
    phone = models.CharField(max_length=50, verbose_name="Număr de Telefon")
    products = models.TextField(verbose_name="Produse de returnat")
    return_reason = models.CharField(
        max_length=50,
        choices=REASON_CHOICES,
        default='nepotrivire',
        verbose_name="Motivul returului"
    )
    refund_method = models.CharField(
        max_length=30,
        choices=REFUND_METHOD_CHOICES,
        default='card',
        verbose_name="Metoda de rambursare"
    )
    iban = models.CharField(max_length=60, blank=True, null=True, verbose_name="Cont IBAN")
    account_holder = models.CharField(max_length=250, blank=True, null=True, verbose_name="Titular Cont")
    observations = models.TextField(blank=True, null=True, verbose_name="Observații suplimentare")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending', verbose_name="Status")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data solicitării")

    class Meta:
        verbose_name = "Solicitare Retur"
        verbose_name_plural = "Solicitări Retur"
        ordering = ['-created_at']

    def __str__(self):
        return f"Retur #{self.id} - Comanda {self.order_number} ({self.full_name})"