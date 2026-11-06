from decimal import Decimal

from django.db import migrations


PRODUCTS = [
    {
        "name": "Coastal White Prawns",
        "slug": "coastal-white-prawns",
        "category": "prawns",
        "description": "Sweet, tender prawns, cleaned and ready for your favourite curry.",
        "image_url": "https://images.unsplash.com/photo-1565680018434-b513d5e5fd47?auto=format&fit=crop&w=900&q=80",
        "price": Decimal("449.00"),
        "compare_at_price": Decimal("520.00"),
        "weight": "500 g · 20–25 pcs",
        "stock": 18,
        "is_featured": True,
    },
    {
        "name": "Tiger Prawns",
        "slug": "tiger-prawns",
        "category": "prawns",
        "description": "Firm, juicy tiger prawns with a naturally rich flavour.",
        "image_url": "https://images.unsplash.com/photo-1625944525533-473f1a3d54e7?auto=format&fit=crop&w=900&q=80",
        "price": Decimal("599.00"),
        "compare_at_price": Decimal("680.00"),
        "weight": "500 g · 8–10 pcs",
        "stock": 12,
        "is_featured": True,
    },
    {
        "name": "Fresh Seer Fish",
        "slug": "fresh-seer-fish",
        "category": "fish",
        "description": "Meaty seer fish steaks, cut fresh for a quick pan fry.",
        "image_url": "https://images.unsplash.com/photo-1510130387422-82bed34b37e9?auto=format&fit=crop&w=900&q=80",
        "price": Decimal("549.00"),
        "compare_at_price": Decimal("620.00"),
        "weight": "500 g · 4–5 steaks",
        "stock": 9,
        "is_featured": True,
    },
    {
        "name": "Blue Swimming Crab",
        "slug": "blue-swimming-crab",
        "category": "crab",
        "description": "Delicate, sweet crab, cleaned and prepared for a coastal masala.",
        "image_url": "https://images.unsplash.com/photo-1559737558-2f5a35f4523b?auto=format&fit=crop&w=900&q=80",
        "price": Decimal("399.00"),
        "compare_at_price": None,
        "weight": "500 g · 2–3 pcs",
        "stock": 7,
        "is_featured": False,
    },
    {
        "name": "Scampi — Large",
        "slug": "large-scampi",
        "category": "prawns",
        "description": "Large, shell-on scampi with a sweet, delicate bite.",
        "image_url": "https://images.unsplash.com/photo-1599084993091-1cb5c0721cc6?auto=format&fit=crop&w=900&q=80",
        "price": Decimal("699.00"),
        "compare_at_price": None,
        "weight": "500 g · 6–8 pcs",
        "stock": 5,
        "is_featured": False,
    },
    {
        "name": "Tender Squid Rings",
        "slug": "tender-squid-rings",
        "category": "shellfish",
        "description": "Mild, tender squid cleaned and sliced for easy cooking.",
        "image_url": "https://images.unsplash.com/photo-1579631542720-3a87824fff86?auto=format&fit=crop&w=900&q=80",
        "price": Decimal("329.00"),
        "compare_at_price": Decimal("380.00"),
        "weight": "500 g",
        "stock": 14,
        "is_featured": False,
    },
]


def seed_products(apps, schema_editor):
    Product = apps.get_model("website", "Product")
    Product.objects.using(schema_editor.connection.alias).bulk_create(
        [Product(**product) for product in PRODUCTS]
    )


def remove_products(apps, schema_editor):
    Product = apps.get_model("website", "Product")
    Product.objects.using(schema_editor.connection.alias).filter(
        slug__in=[product["slug"] for product in PRODUCTS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("website", "0001_initial")]

    operations = [migrations.RunPython(seed_products, remove_products)]
