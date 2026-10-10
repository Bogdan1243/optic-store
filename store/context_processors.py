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
    return {
        'nav_opt_brands': brands['OPT'],
        'nav_sun_brands': brands['SUN'],
        'nav_all_brands': sorted(set(brands['OPT']) | set(brands['SUN'])),
    }
