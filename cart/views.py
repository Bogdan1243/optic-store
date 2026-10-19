from django.shortcuts import render, get_object_or_404, redirect
from .cart import Cart
from store.models import Product, Order, OrderItem
from django.http import JsonResponse
from django.contrib import messages
import stripe
from django.urls import reverse
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
stripe.api_key = settings.STRIPE_SECRET_KEY


def cart_summary(request):
    cart = Cart(request)
    cart_products = cart.get_prods()
    quantities = cart.get_quants()  # <--- Get quantities
    totals = cart.get_total()

    return render(request, "cart_summary.html", {
        "cart_products": cart_products,
        "quantities": quantities,  # <--- Pass them to the template
        "totals": totals
    })


def cart_add(request):
    cart = Cart(request)
    if request.POST.get('action') == 'post':
        product_id = int(request.POST.get('product_id'))

        # 👇 This line is critical! It must securely convert the '1' to an integer.
        product_qty = int(request.POST.get('product_qty', 1))

        product = get_object_or_404(Product, id=product_id)

        # Catch the prescription data...
        pd_val = request.POST.get('pd')

        if pd_val:  # If PD exists, it means they used the prescription form!
            prescription_data = {
                'od_sph': request.POST.get('od_sph'),
                'od_cyl': request.POST.get('od_cyl'),
                'od_axis': request.POST.get('od_axis'),
                'os_sph': request.POST.get('os_sph'),
                'os_cyl': request.POST.get('os_cyl'),
                'os_axis': request.POST.get('os_axis'),
                'pd': pd_val,
            }
        else:
            prescription_data = None  # It was just sunglasses

        # Validate prescription data if provided
        if prescription_data:
            import re
            rx_pattern = re.compile(r'^[+-]?\d{1,2}(\.\d{1,2})?$')
            axis_pattern = re.compile(r'^\d{1,3}$')
            pd_pattern = re.compile(r'^\d{2,3}(\.\d)?$')

            for field in ['od_sph', 'od_cyl', 'os_sph', 'os_cyl']:
                val = prescription_data.get(field, '')
                if val and not rx_pattern.match(val):
                    return JsonResponse({'error': f'Invalid prescription value for {field}'}, status=400)

            for field in ['od_axis', 'os_axis']:
                val = prescription_data.get(field, '')
                if val and (not axis_pattern.match(val) or int(val) > 180):
                    return JsonResponse({'error': f'Invalid axis value for {field} (must be 0-180)'}, status=400)

            pd_value = prescription_data.get('pd', '')
            if pd_value and not pd_pattern.match(pd_value):
                return JsonResponse({'error': 'Invalid PD value'}, status=400)

        selected_size = request.POST.get('selected_size', '').strip()

        # 👇 2. Send it to the Cart Class!
        cart.add(product=product, quantity=1, prescription=prescription_data, selected_size=selected_size)

        cart_quantity = cart.__len__()
        response = JsonResponse({'qty': cart_quantity})
        return response

def cart_delete(request, product_id):
    cart = Cart(request)
    cart.delete(product=product_id)
    return redirect('cart_summary')


def checkout(request):
    cart = Cart(request)
    cart_products = cart.get_prods()
    totals = cart.get_total()

    return render(request, "checkout.html", {
        "cart_products": cart_products,
        "totals": totals
    })


def process_order(request):
    if request.POST:
        cart = Cart(request)
        cart_products = cart.get_prods()
        quantities = cart.get_quants()
        totals = cart.get_total()

        # Get Billing Info
        full_name = request.POST['full_name']
        email = request.POST['email']
        shipping_address = request.POST['shipping_address']

        # Get User
        if request.user.is_authenticated:
            user = request.user
        else:
            user = None

        # 1. Create the Order (Saved as "Unpaid" by default)
        create_order = Order(
            user=user,
            full_name=full_name,
            email=email,
            shipping_address=shipping_address,
            amount_paid=totals,
            paid=False  # <--- Not paid yet!
        )
        create_order.save()

        # 2. Create Order Items and Stripe Line Items
        stripe_line_items = []

        for product in cart_products:
            product_id = str(product.id)
            if product_id in quantities:
                qty = int(quantities[product_id]['qty'])
                # 👇 1. Extract the prescription from the cart dictionary!
                prescription = quantities[product_id].get('prescription')
            else:
                qty = 1
                prescription = None

            # 👇 2. Prepare the medical data
            rx_data = {}
            if prescription:
                rx_data = {
                    'od_sph': prescription.get('od_sph'),
                    'od_cyl': prescription.get('od_cyl'),
                    'od_axis': prescription.get('od_axis'),
                    'os_sph': prescription.get('os_sph'),
                    'os_cyl': prescription.get('os_cyl'),
                    'os_axis': prescription.get('os_axis'),
                    'pd': prescription.get('pd'),
                }

            # 👇 3. Save to DB (using **rx_data to magically unpack the dictionary!)
            order_item = OrderItem(
                order=create_order,
                product=product,
                user=user,
                quantity=qty,
                price=product.price,
                **rx_data
            )
            order_item.save()

            # Add to Stripe List
            stripe_line_items.append({
                'price_data': {
                    'currency': 'ron',  # <--- Romanian Lei 🇷🇴
                    'unit_amount': int(product.price * 100),  # Stripe uses "bani" (cents), so multiply by 100
                    'product_data': {
                        'name': product.brand,
                    },
                },
                'quantity': qty,
            })

        # 3. Create Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=stripe_line_items,
            mode='payment',
            success_url=request.build_absolute_uri(reverse('payment_success')) + f"?order_id={create_order.id}",
            cancel_url=request.build_absolute_uri(reverse('payment_failed')),
        )

        # 4. Redirect User to Stripe (Code 303 is required for redirect)
        return redirect(checkout_session.url, code=303)

    else:
        messages.success(request, "Access Denied")
        return redirect('home')
def cart_update(request):
    cart = Cart(request)
    if request.POST.get('action') == 'post':
        product_id = int(request.POST.get('product_id'))
        product_qty = int(request.POST.get('product_qty'))

        cart.update(product=product_id, quantity=product_qty)

        response = JsonResponse({'qty': product_qty})
        return response


def payment_success(request):
    # Empty the cart
    cart = Cart(request)
    cart.clear()

    # Get the Order ID from the URL
    order_id = request.GET.get('order_id')

    if order_id:
        order = Order.objects.get(id=order_id)
        order.paid = True
        order.save()

        # ... inside payment_success view ...
        order_items = OrderItem.objects.filter(order=order)

        # 👇 --- 1. SEND UPGRADED NOTIFICATION TO YOU --- 👇
        admin_subject = f"New Paid Order! 💸 (Order #{order.id})"
        admin_body = f"Customer: {order.full_name}\nEmail: {order.email}\nTotal: {order.amount_paid} RON\n\n--- ITEMS ORDERED ---\n"

        for item in order_items:
            admin_body += f"\n- {item.quantity}x {item.product.brand} ({item.price} RON)\n"

            # Check if this item has a prescription!
            if item.pd:
                admin_body += f"   [RX Details]\n"
                admin_body += f"   OD (Right): SPH {item.od_sph or '0.00'} | CYL {item.od_cyl or '0.00'} | AXIS {item.od_axis or '0'}\n"
                admin_body += f"   OS (Left) : SPH {item.os_sph or '0.00'} | CYL {item.os_cyl or '0.00'} | AXIS {item.os_axis or '0'}\n"
                admin_body += f"   PD: {item.pd}mm\n"

        send_mail(
            admin_subject,
            admin_body,
            settings.DEFAULT_FROM_EMAIL,
            [settings.ADMIN_NOTIFICATION_EMAIL],
            fail_silently=False
        )

    messages.success(request, "Payment successful! Your glasses are on the way. 🕶️")
    return redirect('home')
def payment_failed(request):
    messages.error(request, "Payment failed. Please try again.")
    return redirect('checkout')