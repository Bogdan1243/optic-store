from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
import datetime

from cart.cart import Cart
from .models import Product, Order, OrderItem, Review
from .forms import ReviewForm, CustomRegisterForm
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.decorators import login_required
# --- 1. PAGES ---

def home(request):
    return render(request, 'landing.html', {})

def about(request):
    return render(request, "about.html", {})

def contact(request):
    return render(request, "contact.html", {})

# --- 2. SHOP & FILTERS ---

# Brand logos shown as the banner on brand pages (files live in static/images/brands/)
BRAND_LOGOS = {
    'armani exchange': 'images/brands/AX_Logo_Digital.svg',
    'dolce&gabbana': 'images/brands/DG_Logo_Digital.svg',
    'emporio armani': 'images/brands/EA_Logo_Digital.svg',
    'michael kors': 'images/brands/MK_Logo_Digital.svg',
    'ray-ban': 'images/brands/RB_Logo_Digital.svg',
    'swarovski': 'images/brands/SK_Logo_Digital.svg',
    'vogue': 'images/brands/VO_Logo_Digital.jpeg',
}


def get_brand_logo(brand_name):
    """Returns the static path of the brand's logo, or None if there is none."""
    if not brand_name or brand_name == 'All':
        return None
    return BRAND_LOGOS.get(brand_name.strip().lower())


def deduplicate_products_by_model(queryset):
    """
    Deduplicates a queryset/list of products by model_code.
    Only the first product for each model_code is kept in the catalog listing.
    Products without model_code remain individual products.
    """
    seen_models = set()
    deduped = []
    for product in queryset:
        if product.model_code:
            if product.model_code not in seen_models:
                seen_models.add(product.model_code)
                deduped.append(product)
        else:
            deduped.append(product)
    return deduped


def shop(request):
    products = Product.objects.all()
    sex_query = request.GET.get('sex')
    brand_query = request.GET.get('brand')

    is_filtered = False  # We will use this to tell HTML to hide "Our Full Collection"

    if sex_query and sex_query != 'All':
        products = products.filter(sex__iexact=sex_query)
        is_filtered = True

    if brand_query and brand_query != 'All':
        products = products.filter(brand__icontains=brand_query)
        is_filtered = True

    products = deduplicate_products_by_model(products)

    return render(request, 'home.html', {
        'products': products,
        'sex_query': sex_query,
        'brand_query': brand_query,
        'brand_logo': get_brand_logo(brand_query),
        'is_filtered': is_filtered,
    })


def filter_by_category(request, cat_code):
    # 1. Grab only the products in this category ('SUN' or 'OPT')
    products = Product.objects.filter(category=cat_code)

    # 2. Check if they are ALSO using the sidebar filters
    sex_query = request.GET.get('sex')
    brand_query = request.GET.get('brand')

    if sex_query and sex_query != 'All':
        products = products.filter(sex__iexact=sex_query)

    if brand_query and brand_query != 'All':
        products = products.filter(brand__icontains=brand_query)

    # 3. Set a nice title for the page
    if cat_code == 'SUN':
        page_title = "Sunglasses Collection"
    else:
        page_title = "Vision & Optical Collection"

    products = deduplicate_products_by_model(products)

    # 4. Render the shop page
    return render(request, 'home.html', {
        'products': products,
        'title': page_title,
        'cat_code': cat_code,
        'sidebar_brands': Product.objects.filter(category=cat_code)
                                         .values_list('brand', flat=True)
                                         .distinct().order_by('brand'),
        'sex_query': sex_query,
        'brand_query': brand_query,
        'brand_logo': get_brand_logo(brand_query),
        'is_filtered': True,
    })

def filter_by_brand(request, brand_name):
    products = Product.objects.filter(brand__icontains=brand_name)
    products = deduplicate_products_by_model(products)
    return render(request, 'home.html', {
        'products': products,
        'title': brand_name,
        'brand_query': brand_name,
        'brand_logo': get_brand_logo(brand_name),
    })


def filter_by_sex(request, sex_name):
    products = Product.objects.filter(sex__iexact=sex_name)
    products = deduplicate_products_by_model(products)
    return render(request, 'home.html', {
        'products': products,
        'title': sex_name
    })

# --- 3. PRODUCTS & AR ---

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    reviews = Review.objects.filter(product=product).order_by('-date_added')

    if request.method == 'POST':
        if request.user.is_authenticated:
            form = ReviewForm(request.POST)
            if form.is_valid():
                review = form.save(commit=False)
                review.product = product
                review.user = request.user
                review.save()
                messages.success(request, "Review submitted successfully!")
                return redirect('product_detail', slug=slug)
        else:
            messages.error(request, "You must be logged in to review.")
            return redirect('login')
    else:
        form = ReviewForm()

    return render(request, 'product_detail.html', {
        'product': product,
        'reviews': reviews,
        'form': form,
        'prescription_enabled': getattr(settings, 'PRESCRIPTION_ENABLED', False),
    })

def try_on(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'try_on.html', {'product': product})

# --- 4. USERS & AUTH ---

def login_user(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, "You have been logged in!")
            return redirect('home')
        else:
            messages.error(request, "There was an error logging in. Please try again.")
            return redirect('login')
    else:
        return render(request, 'login.html', {})

def logout_user(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('home')

def register_user(request):
    if request.method == "POST":
        form = CustomRegisterForm(request.POST) # 👈 Changed here
        if form.is_valid():
            form.save()
            messages.success(request, "Registration successful! You can now log in.")
            return redirect('login')
        else:
            messages.error(request, "Registration failed. Please try again.")
            return render(request, 'register.html', {'form': form})
    else:
        form = CustomRegisterForm() # 👈 Changed here
        return render(request, 'register.html', {'form': form})


@login_required(login_url='login')
def user_profile(request):
    # Grab the user's past orders
    orders = Order.objects.filter(user=request.user).order_by('-date_ordered')

    # Send them to the luxurious profile.html template
    return render(request, 'profile.html', {"orders": orders})


def filter_by_category2(request, cat_code):
    products = Product.objects.filter(category=cat_code)

    sex_query = request.GET.get('sex')
    brand_query = request.GET.get('brand')
    # 👇 Grab the new parameters
    color_query = request.GET.get('color')
    size_query = request.GET.get('size')

    if sex_query and sex_query != 'All':
        products = products.filter(sex__iexact=sex_query)

    if brand_query and brand_query != 'All':
        products = products.filter(brand__icontains=brand_query)

    # 👇 Filter by Color if requested
    if color_query:
        products = products.filter(color__icontains=color_query)

    # 👇 Filter by Size if requested
    if size_query:
        products = products.filter(size__iexact=size_query)

    if cat_code == 'SUN':
        page_title = "Sunglasses Collection"
    else:
        page_title = "Vision & Optical Collection"

    return render(request, 'home.html', {
        'products': products,
        'title': page_title,
        'is_filtered': True,
    })