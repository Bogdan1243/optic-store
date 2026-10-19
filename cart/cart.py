from store.models import Product
class Cart():
    def __init__(self, request):
        self.session = request.session

        # Check if the user already has a 'session_key' for the cart
        cart = self.session.get('session_key')

        # If not, create a new empty cart dictionary
        if 'session_key' not in self.session:
            cart = self.session['session_key'] = {}

        self.cart = cart

    def add(self, product, quantity=1, prescription=None, selected_size=None):
        product_id = str(product.id)
        size_val = (selected_size or '').strip()
        if not size_val:
            size_val = product.size_list[0] if getattr(product, 'size_list', None) else (product.size or '')

        if product_id in self.cart:
            self.cart[product_id]['qty'] = '1'
            if size_val:
                self.cart[product_id]['size'] = size_val
            if prescription:
                self.cart[product_id]['prescription'] = prescription
        else:
            # Add the item to the cart dictionary (always qty 1 since only 1 pair of each product exists)
            self.cart[product_id] = {
                'price': str(product.price),
                'qty': '1',
                'size': size_val,
            }

            if prescription:
                self.cart[product_id]['prescription'] = prescription

        self.session.modified = True

    def get_prods(self):
        product_ids = self.cart.keys()
        # Use those IDs to find the actual products in the DB
        products = Product.objects.filter(id__in=product_ids)
        return products

    def get_total(self):
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids)

        total = 0
        for product in products:
            total = total + product.price

        return total

    def delete(self, product):
        product_id = str(product)

        if product_id in self.cart:
            del self.cart[product_id]

        self.session.modified = True

    def __len__(self):
        return len(self.cart)

    def clear(self):
        # Delete the cart from the session
        del self.session['session_key']
        self.session.modified = True

    def get_quants(self):
        quantities = self.cart
        return quantities

    def update(self, product, quantity):
        product_id = str(product)

        if product_id in self.cart:
            self.cart[product_id]['qty'] = 1

        self.session.modified = True

        thing = self.cart
        return thing