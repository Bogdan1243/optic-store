from django.urls import path
from . import views

urlpatterns =[
    path('', views.cart_summary, name='cart_summary'),
    path('delete/<int:product_id>/', views.cart_delete, name ='cart_delete'),
path('checkout/', views.checkout, name='checkout'),
path('process_order/', views.process_order, name="process_order"),
path('add/', views.cart_add, name='cart_add'), # <--- THIS IS CORRECT ✅
path('update/', views.cart_update, name='cart_update'),
path('payment_success/', views.payment_success, name='payment_success'),
    path('payment_failed/', views.payment_failed, name='payment_failed'),
]
