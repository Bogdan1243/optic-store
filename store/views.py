from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
import datetime

from cart.cart import Cart
from .models import Product, Order, OrderItem, Review, ReturnRequest
from .forms import ReviewForm, CustomRegisterForm, ReturnRequestForm
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
# --- 1. PAGES ---

def home(request):
    return render(request, 'landing.html', {})

def about(request):
    return render(request, "about.html", {})

def contact(request):
    return render(request, "contact.html", {})


def _get_initial_return_data(request):
    initial = {}
    if request.user.is_authenticated:
        full_name = f"{request.user.first_name} {request.user.last_name}".strip()
        initial['full_name'] = full_name or request.user.username
        initial['email'] = request.user.email
    order_param = request.GET.get('order', '').strip()
    if order_param:
        initial['order_number'] = order_param
    return initial


def _process_return_submission(request, form):
    return_req = form.save(commit=False)
    if request.user.is_authenticated:
        return_req.user = request.user
    try:
        return_req.save()
    except Exception:
        pass

    # Attempt to send email notification to store admin
    try:
        admin_email = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', None) or 'clinica.imagister@gmail.com'
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or admin_email
        subject = f"Solicitare Retur Nouă - Comanda {return_req.order_number}"
        body = (
            f"A fost înregistrată o nouă solicitare de retur:\n\n"
            f"Număr Comandă: {return_req.order_number}\n"
            f"Nume Client: {return_req.full_name}\n"
            f"Email: {return_req.email}\n"
            f"Telefon: {return_req.phone}\n"
            f"Produse de returnat: {return_req.products}\n"
            f"Motiv retur: {return_req.get_return_reason_display()}\n"
            f"Metodă rambursare: {return_req.get_refund_method_display()}\n"
            f"IBAN: {return_req.iban or '-'}\n"
            f"Titular Cont: {return_req.account_holder or '-'}\n"
            f"Observații: {return_req.observations or '-'}\n"
        )
        send_mail(subject, body, from_email, [admin_email], fail_silently=True)
    except Exception:
        pass


def livrare_si_retur(request):
    if request.method == 'POST':
        form = ReturnRequestForm(request.POST)
        if form.is_valid():
            _process_return_submission(request, form)
            messages.success(
                request,
                "Solicitarea dvs. de retur a fost înregistrată cu succes! "
                "Vă vom trimite un e-mail de confirmare după recepționarea și verificarea coletului."
            )
            return redirect('livrare_si_retur')
        else:
            messages.error(request, "Vă rugăm să verificați câmpurile formularului de retur.")
    else:
        form = ReturnRequestForm(initial=_get_initial_return_data(request))

    return render(request, "livrare_si_retur.html", {"form": form})


def formular_retur(request):
    if request.method == 'POST':
        form = ReturnRequestForm(request.POST)
        if form.is_valid():
            _process_return_submission(request, form)
            messages.success(
                request,
                "Solicitarea dvs. de retur a fost înregistrată cu succes! "
                "Vă vom trimite un e-mail de confirmare după recepționarea și verificarea coletului."
            )
            return redirect('formular_retur')
        else:
            messages.error(request, "Vă rugăm să verificați câmpurile formularului de retur.")
    else:
        form = ReturnRequestForm(initial=_get_initial_return_data(request))

    return render(request, "formular_retur.html", {"form": form})


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


def filter_products_by_search(queryset, search_query):
    """Filters products based on brand name or product code (model_code / slug)."""
    if not search_query:
        return queryset
    tokens = search_query.strip().split()
    for token in tokens:
        token_no_zero = token.lstrip('0') or token
        token_q = (
            Q(brand__icontains=token) |
            Q(model_code__icontains=token) |
            Q(slug__icontains=token)
        )
        if token_no_zero != token:
            token_q |= Q(model_code__icontains=token_no_zero) | Q(slug__icontains=token_no_zero)
        if '-' in token:
            parts = [p for p in token.split('-') if p]
            if len(parts) > 1:
                parts_q = Q()
                for part in parts:
                    parts_q &= (
                        Q(brand__icontains=part) |
                        Q(model_code__icontains=part) |
                        Q(slug__icontains=part)
                    )
                token_q |= parts_q
        queryset = queryset.filter(token_q)
    return queryset


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


def paginate_products(products, request, per_page=20):
    paginator = Paginator(products, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    current = page_obj.number
    total = paginator.num_pages

    if total <= 4:
        page_obj.elided_pages = list(range(1, total + 1))
    elif current == 1:
        page_obj.elided_pages = [1, 2, 3, paginator.ELLIPSIS, total]
    elif current >= total - 1:
        page_obj.elided_pages = [total - 2, total - 1, total]
    else:
        pages = [current - 1, current, current + 1]
        if pages[-1] < total:
            if pages[-1] == total - 1:
                pages.append(total)
            else:
                pages.extend([paginator.ELLIPSIS, total])
        page_obj.elided_pages = pages

    return page_obj


def shop(request):
    products = Product.objects.all()
    sex_query = request.GET.get('sex')
    brand_query = request.GET.get('brand')
    search_query = request.GET.get('q', '').strip()

    is_filtered = False  # We will use this to tell HTML to hide "Our Full Collection"

    if sex_query and sex_query != 'All':
        products = products.filter(sex__iexact=sex_query)
        is_filtered = True

    if brand_query and brand_query != 'All':
        products = products.filter(brand__icontains=brand_query)
        is_filtered = True

    if search_query:
        products = filter_products_by_search(products, search_query)
        is_filtered = True

    products = deduplicate_products_by_model(products)
    products = paginate_products(products, request, 20)

    return render(request, 'home.html', {
        'products': products,
        'sex_query': sex_query,
        'brand_query': brand_query,
        'search_query': search_query,
        'brand_logo': get_brand_logo(brand_query) or get_brand_logo(search_query),
        'is_filtered': is_filtered,
    })


def filter_by_category(request, cat_code):
    # 1. Grab only the products in this category ('SUN' or 'OPT')
    products = Product.objects.filter(category=cat_code)

    # 2. Check if they are ALSO using the sidebar filters
    sex_query = request.GET.get('sex')
    brand_query = request.GET.get('brand')
    search_query = request.GET.get('q', '').strip()

    if sex_query and sex_query != 'All':
        products = products.filter(sex__iexact=sex_query)

    if brand_query and brand_query != 'All':
        products = products.filter(brand__icontains=brand_query)

    if search_query:
        products = filter_products_by_search(products, search_query)

    # 3. Set a nice title for the page
    if cat_code == 'SUN':
        page_title = "Ochelari de soare"
    else:
        page_title = "Ochelari de vedere"

    products = deduplicate_products_by_model(products)
    products = paginate_products(products, request, 20)

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
        'search_query': search_query,
        'brand_logo': get_brand_logo(brand_query) or get_brand_logo(search_query),
        'is_filtered': True,
    })

def filter_by_brand(request, brand_name):
    products = Product.objects.filter(brand__icontains=brand_name)
    products = deduplicate_products_by_model(products)
    products = paginate_products(products, request, 20)
    return render(request, 'home.html', {
        'products': products,
        'title': brand_name,
        'brand_query': brand_name,
        'brand_logo': get_brand_logo(brand_name),
    })


def filter_by_sex(request, sex_name):
    products = Product.objects.filter(sex__iexact=sex_name)
    products = deduplicate_products_by_model(products)
    products = paginate_products(products, request, 20)
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
        page_title = "Ochelari de soare"
    else:
        page_title = "Ochelari de vedere"

    products = deduplicate_products_by_model(products)
    products = paginate_products(products, request, 20)

    return render(request, 'home.html', {
        'products': products,
        'title': page_title,
        'is_filtered': True,
    })


# --- 5. FAVOURITES / WISHLIST ---

def favourites_view(request):
    from django.http import JsonResponse  # noqa: F401
    fav_raw = request.session.get('favourites', [])
    fav_ids = []
    for pid in fav_raw:
        try:
            fav_ids.append(int(pid))
        except (ValueError, TypeError):
            pass

    products_by_id = {p.id: p for p in Product.objects.filter(id__in=fav_ids)}
    favourite_products = [products_by_id[pid] for pid in fav_ids if pid in products_by_id]

    return render(request, 'favourites.html', {
        'products': favourite_products,
    })


def toggle_favourite(request, pk):
    from django.http import JsonResponse
    product = get_object_or_404(Product, pk=pk)
    fav_raw = request.session.get('favourites', [])
    fav_ids = []
    for pid in fav_raw:
        try:
            val = int(pid)
            if val not in fav_ids:
                fav_ids.append(val)
        except (ValueError, TypeError):
            pass

    if product.id in fav_ids:
        fav_ids.remove(product.id)
        is_favourite = False
    else:
        fav_ids.append(product.id)
        is_favourite = True

    request.session['favourites'] = fav_ids
    request.session.modified = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.method == 'POST':
        return JsonResponse({
            'is_favourite': is_favourite,
            'count': len(fav_ids),
            'product_id': product.id,
        })

    return redirect(request.META.get('HTTP_REFERER', 'favourites'))