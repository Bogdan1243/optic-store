from .models import Product


def nav_brands(request):
    """Brands available per category, used by the navbar mega-menu."""
    rows = (
        Product.objects.values_list('category', 'brand')
        .distinct()
        .order_by('brand')
    )
    brands = {'OPT': [], 'SUN': []}
    for category, brand in rows:
        if category in brands and brand and brand not in brands[category]:
            brands[category].append(brand)
    fav_raw = request.session.get('favourites', []) if hasattr(request, 'session') else []
    favourite_ids = []
    for pid in fav_raw:
        try:
            favourite_ids.append(int(pid))
        except (ValueError, TypeError):
            pass

    return {
        'nav_opt_brands': brands['OPT'],
        'nav_sun_brands': brands['SUN'],
        'nav_all_brands': sorted(set(brands['OPT']) | set(brands['SUN'])),
        'favourite_ids': favourite_ids,
        'favourites_count': len(favourite_ids),
    }
