from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("login/", views.staff_login, name="login"),
    path("", views.overview, name="overview"),
    path("products/", views.products, name="products"),
    path("products/add/", views.product_create, name="product_create"),
    path("products/<int:product_id>/edit/", views.product_edit, name="product_edit"),
    path("stores/", views.stores, name="stores"),
    path("stores/add/", views.store_create, name="store_create"),
    path("stores/<int:store_id>/edit/", views.store_edit, name="store_edit"),
    path("orders/", views.orders, name="orders"),
    path("contacts/", views.contacts, name="contacts"),
    path("messages/", views.inquiries, name="inquiries"),
    path("messages/<int:inquiry_id>/resolve/", views.resolve_inquiry, name="resolve_inquiry"),
    path("orders/<int:order_id>/status/", views.update_order_status, name="update_order_status"),
]
