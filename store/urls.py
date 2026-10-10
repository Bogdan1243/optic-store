from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [path('',views.home,name='home'),
path('shop/', views.shop, name='shop'),
               path('product/<slug:slug>/', views.product_detail, name='product_detail'),
               path('login/', views.login_user, name='login'),
               path('logout/', views.logout_user, name='logout'),
path('register/', views.register_user, name='register'),
path('about/', views.about, name='about'),
path('contact/', views.contact, name='contact'),
path('try_on/<int:pk>/', views.try_on, name='try_on'),
path('brand/<str:brand_name>/', views.filter_by_brand, name='filter_by_brand'),
path('gender/<str:sex_name>/', views.filter_by_sex, name='filter_by_sex'),
path('category/<str:cat_code>/', views.filter_by_category, name='category'),
path('profile/', views.user_profile, name='profile'),
path('password-reset/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html'), name='password_reset'),
path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), name='password_reset_confirm'),
path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),
               ]