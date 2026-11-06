from django.urls import path

from . import views

app_name = "website"

urlpatterns = [
    path("", views.home, name="home"),
    path("products/", views.products, name="products"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("contact/submit/", views.contact_submit, name="contact_submit"),
    path("register/", views.register, name="register"),
    path("login/", views.customer_login, name="login"),
    path("logout/", views.customer_logout, name="logout"),
    path("my-orders/", views.track_orders, name="track_orders"),
    path("track-order/", views.track_guest_order, name="track_guest_order"),
    path("delivery-area/", views.select_delivery_area, name="select_delivery_area"),
    path("delivery-area/dismiss/", views.dismiss_delivery_prompt, name="dismiss_delivery_prompt"),
    path("delivery-area/lookup/", views.lookup_delivery_postcode, name="lookup_delivery_postcode"),
    path("delivery-area/location/", views.lookup_location_postcode, name="lookup_location_postcode"),
    path("cart/", views.cart, name="cart"),
    path("cart/add/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path("cart/update/<int:product_id>/", views.update_cart, name="update_cart"),
    path("cart/remove/<int:product_id>/", views.remove_from_cart, name="remove_from_cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("order/<str:reference>/", views.order_success, name="order_success"),
]
