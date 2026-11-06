import secrets
import string

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.urls import reverse


class Product(models.Model):
    class Category(models.TextChoices):
        FISH = "fish", "Fresh fish"
        PRAWNS = "prawns", "Prawns"
        CRAB = "crab", "Crab"
        SHELLFISH = "shellfish", "Shellfish"

    name = models.CharField(max_length=140)
    slug = models.SlugField(unique=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True)
    price = models.DecimalField(max_digits=9, decimal_places=2, validators=[MinValueValidator(0)])
    compare_at_price = models.DecimalField(
        max_digits=9, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    weight = models.CharField(max_length=40, default="500 g")
    stock = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_featured", "name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("website:home")

    @property
    def discount_percent(self):
        if self.compare_at_price and self.compare_at_price > self.price:
            return round((self.compare_at_price - self.price) * 100 / self.compare_at_price)
        return None


class Store(models.Model):
    name = models.CharField(max_length=120)
    address = models.CharField(max_length=240, blank=True)
    city = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    delivery_radius_km = models.DecimalField(
        max_digits=6, decimal_places=2, default=15,
        validators=[MinValueValidator(0.01)],
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def clean(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValidationError("Enter both latitude and longitude for location-based routing.")

    def __str__(self):
        return self.name


class StorePincode(models.Model):
    store = models.ForeignKey(Store, related_name="service_areas", on_delete=models.CASCADE)
    postcode = models.CharField(
        max_length=6,
        validators=[RegexValidator(r"^\d{6}$", "Enter a valid six-digit PIN code.")],
    )
    priority = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["postcode", "-priority", "store__name"]
        constraints = [
            models.UniqueConstraint(fields=["store", "postcode"], name="unique_store_service_postcode")
        ]

    def __str__(self):
        return f"{self.postcode} — {self.store.name}"


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONFIRMED = "confirmed", "Confirmed"
        PREPARING = "preparing", "Preparing"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for delivery"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    reference = models.CharField(max_length=12, unique=True, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="seafood_orders",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    store = models.ForeignKey(
        Store,
        related_name="orders",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=240)
    city = models.CharField(max_length=100)
    postcode = models.CharField(max_length=12)
    notes = models.CharField(max_length=400, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.reference:
            super().save(*args, **kwargs)
            return

        using = kwargs.get("using")
        for _ in range(20):
            self.reference = "".join(
                secrets.choice(string.ascii_uppercase + string.digits)
                for _ in range(6)
            )
            try:
                with transaction.atomic(using=using):
                    super().save(*args, **kwargs)
                return
            except IntegrityError:
                if not type(self).objects.using(using).filter(reference=self.reference).exists():
                    raise
        self.reference = ""
        raise RuntimeError("Could not generate a unique six-character order reference.")

    def __str__(self):
        return f"Order {self.reference}"


class CustomerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="customer_profile",
        on_delete=models.CASCADE,
    )
    phone = models.CharField(max_length=16, unique=True)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.phone})"


class ContactInquiry(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=24, blank=True)
    subject = models.CharField(max_length=160)
    message = models.TextField(max_length=3000)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "contact inquiry"
        verbose_name_plural = "contact inquiries"

    def __str__(self):
        return f"{self.subject} — {self.name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name="order_items", on_delete=models.PROTECT)
    product_name = models.CharField(max_length=140)
    unit_price = models.DecimalField(max_digits=9, decimal_places=2)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    def __str__(self):
        return f"{self.quantity} × {self.product_name}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity
