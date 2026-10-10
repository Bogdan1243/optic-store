from .cart import Cart

def cart(request):
    #Return the defualt data from our Cart
    return {'cart': Cart(request)}

