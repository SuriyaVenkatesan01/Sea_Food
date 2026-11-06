from django.contrib import admin

from .models import ContactInquiry, CustomerProfile, Order, OrderItem, Product, Store, StorePincode


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock", "is_active", "is_featured")
    list_filter = ("category", "is_active", "is_featured")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("price", "stock", "is_active", "is_featured")


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone")
    search_fields = ("user__email", "user__first_name", "user__last_name", "phone")


@admin.register(ContactInquiry)
class ContactInquiryAdmin(admin.ModelAdmin):
    list_display = ("subject", "name", "email", "phone", "is_resolved", "created_at")
    list_filter = ("is_resolved", "created_at")
    search_fields = ("name", "email", "phone", "subject", "message")
    readonly_fields = ("created_at",)
    list_editable = ("is_resolved",)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "product_name", "unit_price", "quantity")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "full_name", "phone", "store", "total", "status", "created_at")
    list_filter = ("store", "status", "created_at")
    search_fields = ("reference", "full_name", "phone", "email", "store__name")
    readonly_fields = ("reference", "subtotal", "delivery_fee", "total", "created_at")
    inlines = [OrderItemInline]


class StorePincodeInline(admin.TabularInline):
    model = StorePincode
    extra = 1
    fields = ("postcode", "priority")
    ordering = ("postcode", "-priority")


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "latitude", "longitude", "delivery_radius_km", "is_active")
    list_filter = ("is_active", "city")
    search_fields = ("name", "city", "service_areas__postcode")
    inlines = [StorePincodeInline]
