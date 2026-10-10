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

    # 👇 Shifted left! Now it is a proper class method, just like __init__
    def add(self, product, quantity=1, prescription=None):
        product_id = str(product.id)
        product_qty = str(quantity)

        if product_id in self.cart:
            pass  # Item is already in cart
        else:
            # Add the item to the cart dictionary
            self.cart[product_id] = {'price': str(product.price), 'qty': product_qty}

            # 👇 Attach the prescription to this specific pair of glasses!
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
            cart_item = self.cart[str(product.id)]

            # 👇 Force the string back into an integer!
            quantity = int(cart_item['qty'])

            total = total + (product.price * quantity)

        return total

    def delete(self, product):
        product_id = str(product)

        if product_id in self.cart:
            del self.cart[product_id]

        self.session.modified = True

    def __len__(self):
        # We need to explicitly convert the string 'qty' back to an integer to sum it up!
        return sum(int(item['qty']) for item in self.cart.values())

    def clear(self):
        # Delete the cart from the session
        del self.session['session_key']
        self.session.modified = True

    def get_quants(self):
        quantities = self.cart
        return quantities

    def update(self, product, quantity):
        product_id = str(product)
        product_qty = int(quantity)

        if product_id in self.cart:
            self.cart[product_id]['qty'] = product_qty

        self.session.modified = True

        # Optional: Return the new cart object if needed, but not strictly necessary here
        thing = self.cart
        return thing