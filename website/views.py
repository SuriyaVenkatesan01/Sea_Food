import json
import logging
import smtplib
from decimal import Decimal
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from .forms import (
    CheckoutForm,
    ContactInquiryForm,
    CustomerAuthenticationForm,
    CustomerRegistrationForm,
)
from .locations import parse_coordinates, resolve_delivery_area, selected_delivery_area
from .models import CustomerProfile, Order, OrderItem, Product

DELIVERY_FEE = Decimal("49.00")
FREE_DELIVERY_FROM = Decimal("799.00")
logger = logging.getLogger(__name__)


def _cart_products(request):
    cart = request.session.get("cart", {})
    products = Product.objects.filter(is_active=True, id__in=cart.keys())
    return [
        {"product": product, "quantity": min(int(cart.get(str(product.id), 0)), product.stock)}
        for product in products
        if product.stock > 0 and int(cart.get(str(product.id), 0)) > 0
    ]


def _cart_totals(items):
    subtotal = sum((item["product"].price * item["quantity"] for item in items), Decimal("0.00"))
    delivery_fee = Decimal("0.00") if subtotal >= FREE_DELIVERY_FROM or not subtotal else DELIVERY_FEE
    return subtotal, delivery_fee, subtotal + delivery_fee


def _category_tiles():
    active_products = Product.objects.filter(is_active=True)
    tiles = [
        {
            "value": "",
            "label": "All seafood",
            "image_url": active_products.exclude(image_url="")
            .values_list("image_url", flat=True)
            .first(),
        }
    ]
    for value, label in Product.Category.choices:
        tiles.append(
            {
                "value": value,
                "label": label,
                "image_url": active_products.filter(category=value)
                .exclude(image_url="")
                .values_list("image_url", flat=True)
                .first(),
            }
        )
    return tiles


def _product_listing_context(request, catalog_url):
    products = Product.objects.filter(is_active=True)
    category = request.GET.get("category", "")
    search = request.GET.get("q", "").strip()
    if category in Product.Category.values:
        products = products.filter(category=category)
    if search:
        products = products.filter(name__icontains=search)
    context = {
        "products": products,
        "categories": Product.Category.choices,
        "category_tiles": _category_tiles(),
        "active_category": category,
        "search": search,
        "catalog_url": catalog_url,
    }
    return context


def home(request):
    context = _product_listing_context(request, reverse("website:home"))
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "website/partials/shop_content.html", context)
    return render(request, "website/home.html", context)


def products(request):
    context = _product_listing_context(request, reverse("website:products"))
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "website/partials/shop_content.html", context)
    return render(request, "website/products.html", context)


def about(request):
    return render(request, "website/about.html")


def contact(request):
    return render(
        request,
        "website/contact.html",
        {"contact_form": ContactInquiryForm(), "contact_form_invalid": False},
    )


def contact_submit(request):
    if request.method != "POST":
        return redirect("website:contact")
    form = ContactInquiryForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Thanks for reaching out. Your message has been sent.")
        return redirect("website:contact")
    return render(
        request,
        "website/contact.html",
        {
            "contact_form": form,
            "contact_form_invalid": True,
        },
    )


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard:overview" if request.user.is_staff else "website:track_orders")
    form = CustomerRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your account is ready. Sign in to continue.")
        return redirect("website:login")
    return render(request, "website/register.html", {"form": form})


def customer_login(request):
    if request.user.is_authenticated:
        return redirect("dashboard:overview" if request.user.is_staff else "website:track_orders")
    form = CustomerAuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        if user.is_staff or CustomerProfile.objects.filter(user=user).exists():
            login(request, user)
            next_url = request.POST.get("next", "")
            if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            return redirect("dashboard:overview" if user.is_staff else "website:track_orders")
        form.add_error(None, "This account does not have a customer profile.")
    return render(
        request,
        "website/login.html",
        {"form": form, "next": request.POST.get("next", request.GET.get("next", ""))},
    )


@require_POST
def customer_logout(request):
    logout(request)
    messages.info(request, "You have been signed out.")
    return redirect("website:home")


def _add_tracking_steps(order):
    stages = (
        (Order.Status.NEW, "Created"),
        (Order.Status.CONFIRMED, "Confirmed"),
        (Order.Status.PREPARING, "Packing"),
        (Order.Status.OUT_FOR_DELIVERY, "Dispatched"),
        (Order.Status.DELIVERED, "Delivered"),
    )
    order.tracking_steps = []
    if order.status == Order.Status.CANCELLED:
        return order

    current_index = next(
        (index for index, (status, _) in enumerate(stages) if status == order.status),
        0,
    )
    order.tracking_steps = [
        {
            "label": label,
            "state": "complete" if index < current_index else "current" if index == current_index else "upcoming",
        }
        for index, (_, label) in enumerate(stages)
    ]
    return order


@login_required(login_url="website:login")
def track_orders(request):
    try:
        profile = request.user.customer_profile
    except CustomerProfile.DoesNotExist:
        messages.error(request, "Order tracking is available from a customer account.")
        return redirect("website:home")
    search_phone = ""
    orders = Order.objects.none()
    if request.method == "POST":
        search_phone = "".join(char for char in request.POST.get("phone", "") if char.isdigit())
        if search_phone == profile.phone:
            orders = list(
                Order.objects.filter(customer=request.user, phone=profile.phone)
                .prefetch_related("items")
                .order_by("-created_at")
            )
            orders = [_add_tracking_steps(order) for order in orders]
            if not orders:
                messages.info(request, "No orders were found for your phone number yet.")
        else:
            messages.error(request, "Enter the phone number registered to your account.")
    return render(
        request,
        "website/track_orders.html",
        {"orders": orders, "profile": profile, "search_phone": search_phone},
    )


def track_guest_order(request):
    orders = []
    reference = request.GET.get("reference", "").strip()
    phone = ""
    if request.method == "POST":
        lookup = request.POST.get("lookup", "").strip()
        reference = request.POST.get("reference", "").strip()
        phone = "".join(char for char in request.POST.get("phone", "") if char.isdigit())
        if lookup:
            lookup_digits = "".join(char for char in lookup if char.isdigit())
            is_formatted_phone = all(
                character.isdigit() or character in "+()- .\t" for character in lookup
            )
            if is_formatted_phone and 7 <= len(lookup_digits) <= 15:
                phone = lookup_digits
                orders = list(
                    Order.objects.filter(phone=phone)
                    .prefetch_related("items")
                    .order_by("-created_at")[:20]
                )
            else:
                reference = lookup
                order = (
                    Order.objects.filter(reference__iexact=reference)
                    .prefetch_related("items")
                    .first()
                )
                orders = [order] if order else []
        elif reference and 7 <= len(phone) <= 15:
            order = (
                Order.objects.filter(reference__iexact=reference, phone=phone)
                .prefetch_related("items")
                .first()
            )
            orders = [order] if order else []

        orders = [_add_tracking_steps(order) for order in orders]
        if not orders:
            messages.error(request, "We couldn’t find an order matching those details.")
    return render(
        request,
        "website/track_guest_order.html",
        {"orders": orders, "reference": reference, "phone": phone},
    )


def _send_order_confirmation(request, order):
    if not order.email:
        return False

    tracking_path = reverse("website:track_guest_order")
    tracking_url = request.build_absolute_uri(
        f"{tracking_path}?{urlencode({'reference': order.reference})}"
    )
    context = {
        "order": order,
        "tracking_url": tracking_url,
        "company_name": settings.COMPANY_NAME,
    }
    message = EmailMultiAlternatives(
        subject=f"Your {settings.COMPANY_NAME} order {order.reference}",
        body=render_to_string("website/email/order_confirmation.txt", context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.email],
    )
    message.attach_alternative(
        render_to_string("website/email/order_confirmation.html", context),
        "text/html",
    )
    try:
        sent = message.send(fail_silently=False)
    except (OSError, smtplib.SMTPException):
        logger.exception("Could not send confirmation email for order %s", order.reference)
        messages.warning(
            request,
            "Your order is placed, but we could not send the invoice email. Please save your order reference.",
        )
        return False
    if sent != 1:
        logger.error("Confirmation email was not accepted for order %s", order.reference)
        messages.warning(
            request,
            "Your order is placed, but we could not send the invoice email. Please save your order reference.",
        )
        return False

    messages.success(request, f"Your invoice and tracking link were sent to {order.email}.")
    return True


@require_POST
def select_delivery_area(request):
    postcode = request.POST.get("postcode", "").strip()
    latitude = longitude = None
    coordinate_error = None
    try:
        latitude, longitude = parse_coordinates(
            request.POST.get("latitude", ""),
            request.POST.get("longitude", ""),
        )
    except ValueError as error:
        coordinate_error = str(error)
    area = (
        resolve_delivery_area(postcode, latitude, longitude)
        if coordinate_error is None and len(postcode) == 6 and postcode.isdigit()
        else None
    )
    if coordinate_error:
        messages.error(request, coordinate_error)
    elif area is None:
        if latitude is not None:
            messages.error(request, "No store serving that PIN code is within delivery range of your location.")
        else:
            messages.error(request, "We don’t currently deliver to that PIN code. Please choose a supported area.")
    if area is not None:
        request.session["delivery_postcode"] = area["postcode"]
        request.session["delivery_store_id"] = area["store"].id
        request.session.pop("delivery_prompt_dismissed", None)
        distance_message = f", {area['distance_km']} km away" if area["distance_km"] is not None else ""
        request.session.set_expiry(60 * 60 * 24 * 30)
        messages.success(
            request,
            f"Delivery area set to {area['postcode']} ({area['store'].name}{distance_message}).",
        )
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("website:home")


@require_POST
def dismiss_delivery_prompt(request):
    request.session["delivery_prompt_dismissed"] = True
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("website:home")


@require_GET
def lookup_delivery_postcode(request):
    postcode = request.GET.get("postcode", "").strip()
    if len(postcode) != 6 or not postcode.isdigit():
        return JsonResponse({"error": "Enter a valid six-digit PIN code."}, status=400)
    try:
        latitude, longitude = parse_coordinates(
            request.GET.get("latitude", ""),
            request.GET.get("longitude", ""),
        )
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    try:
        with urlopen(f"https://api.postalpincode.in/pincode/{postcode}", timeout=4) as response:
            data = json.loads(response.read())
    except (URLError, TimeoutError, json.JSONDecodeError):
        return JsonResponse(
            {"error": "The online PIN lookup is unavailable. Checking store coverage instead."},
            status=503,
        )

    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        return JsonResponse({"error": "The PIN lookup returned an invalid response."}, status=502)

    result = data[0]
    if result.get("Status") != "Success":
        return JsonResponse(
            {"valid": False, "serviceable": False, "message": "That PIN code was not found."}
        )

    post_offices = result.get("PostOffice")
    if not isinstance(post_offices, list) or not post_offices or not isinstance(post_offices[0], dict):
        return JsonResponse({"error": "The PIN lookup returned no area details."}, status=502)

    office = post_offices[0]
    area = (
        resolve_delivery_area(postcode, latitude, longitude)
        if latitude is not None
        else resolve_delivery_area(postcode)
    )
    location = ", ".join(
        part for part in (office.get("District"), office.get("State")) if isinstance(part, str) and part
    )
    if area is None:
        message = (
            f"No active store is within its delivery radius of your location."
            if latitude is not None
            else f"We do not currently deliver to {postcode}."
        )
        return JsonResponse(
            {
                "valid": True,
                "serviceable": False,
                "location": location,
                "message": message,
            }
        )
    return JsonResponse(
        {
            "valid": True,
            "serviceable": True,
            "location": location,
            "store": area["store"].name,
            "distance_km": str(area["distance_km"]) if area["distance_km"] is not None else None,
            "message": (
                f"Delivery available in {location} through {area['store'].name}"
                + (
                    f", {area['distance_km']} km from your location."
                    if area["distance_km"] is not None
                    else "."
                )
            ),
        }
    )


@require_GET
def lookup_location_postcode(request):
    try:
        latitude, longitude = parse_coordinates(
            request.GET.get("latitude", ""),
            request.GET.get("longitude", ""),
        )
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    if latitude is None or longitude is None:
        return JsonResponse({"error": "Location coordinates are required."}, status=400)
    if not settings.GOOGLE_MAPS_API_KEY:
        return JsonResponse(
            {"error": "Location-to-PIN lookup is not configured. Enter your PIN code manually."},
            status=503,
        )

    query = urlencode(
        {
            "latlng": f"{latitude},{longitude}",
            "key": settings.GOOGLE_MAPS_API_KEY,
            "result_type": "postal_code",
        }
    )
    try:
        with urlopen(f"https://maps.googleapis.com/maps/api/geocode/json?{query}", timeout=4) as response:
            data = json.loads(response.read())
    except (URLError, TimeoutError, json.JSONDecodeError):
        return JsonResponse(
            {"error": "Google location lookup is unavailable. Enter your PIN code manually."},
            status=503,
        )

    if not isinstance(data, dict):
        return JsonResponse({"error": "Google returned an invalid location response."}, status=502)
    if data.get("status") != "OK" or not isinstance(data.get("results"), list):
        return JsonResponse(
            {"error": "Could not find a PIN code for this location. Enter it manually."},
            status=404,
        )

    for result in data["results"]:
        if not isinstance(result, dict):
            continue
        components = result.get("address_components", [])
        if not isinstance(components, list):
            continue
        for component in components:
            if not isinstance(component, dict):
                continue
            types = component.get("types", [])
            postcode = component.get("long_name")
            if (
                isinstance(types, list)
                and "postal_code" in types
                and isinstance(postcode, str)
                and len(postcode) == 6
                and postcode.isdigit()
            ):
                return JsonResponse({"postcode": postcode})

    return JsonResponse(
        {"error": "No six-digit PIN code was found for this location. Enter it manually."},
        status=404,
    )


def cart(request):
    items = _cart_products(request)
    subtotal, delivery_fee, total = _cart_totals(items)
    return render(
        request,
        "website/cart.html",
        {
            "items": items,
            "subtotal": subtotal,
            "delivery_fee": delivery_fee,
            "total": total,
            "free_delivery_remaining": max(Decimal("0.00"), FREE_DELIVERY_FROM - subtotal),
        },
    )


@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)
    if product.stock < 1:
        messages.error(request, f"{product.name} is currently out of stock.")
        return redirect("website:home")
    cart_items = request.session.setdefault("cart", {})
    key = str(product.id)
    cart_items[key] = min(int(cart_items.get(key, 0)) + 1, product.stock)
    request.session.modified = True
    messages.success(request, f"{product.name} added to your basket.")
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("website:home")


@require_POST
def update_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)
    cart_items = request.session.get("cart", {})
    key = str(product.id)
    try:
        quantity = int(request.POST.get("quantity", "1"))
    except ValueError:
        quantity = 1
    if quantity <= 0 or product.stock <= 0:
        cart_items.pop(key, None)
    else:
        cart_items[key] = min(quantity, product.stock)
    request.session["cart"] = cart_items
    return redirect("website:cart")


@require_POST
def remove_from_cart(request, product_id):
    cart_items = request.session.get("cart", {})
    cart_items.pop(str(product_id), None)
    request.session["cart"] = cart_items
    return redirect("website:cart")


def checkout(request):
    items = _cart_products(request)
    if not items:
        messages.info(request, "Your basket is empty. Add some fresh seafood to get started.")
        return redirect("website:home")
    subtotal, delivery_fee, total = _cart_totals(items)
    postcode = request.session.get("delivery_postcode", "")
    area = (
        selected_delivery_area(postcode, request.session.get("delivery_store_id"))
        if postcode
        else None
    )
    if area is None:
        request.session.pop("delivery_postcode", None)
        request.session.pop("delivery_store_id", None)
        messages.error(request, "Choose a supported delivery PIN code before checkout.")
        return redirect("website:home")
    customer_profile = None
    if request.user.is_authenticated and not request.user.is_staff:
        customer_profile = CustomerProfile.objects.filter(user=request.user).first()
    initial = {"postcode": area["postcode"]}
    if customer_profile:
        initial["phone"] = customer_profile.phone
        initial["email"] = request.user.email
        initial["full_name"] = request.user.get_full_name()
    form = CheckoutForm(request.POST or None, initial=initial)
    if request.method == "POST":
        if form.is_valid() and form.cleaned_data["postcode"] != area["postcode"]:
            form.add_error("postcode", "This must match your selected delivery PIN code.")
        if not form.is_valid():
            return render(
                request,
                "website/checkout.html",
                {
                    "items": items, "subtotal": subtotal, "delivery_fee": delivery_fee,
                    "total": total, "form": form, "delivery_area": area,
                },
            )
        try:
            with transaction.atomic():
                locked_products = {
                    product.id: product
                    for product in Product.objects.select_for_update().filter(
                        id__in=[item["product"].id for item in items], is_active=True
                    )
                }
                for item in items:
                    product = locked_products.get(item["product"].id)
                    if product is None or product.stock < item["quantity"]:
                        raise ValueError(f"{item['product'].name} no longer has enough stock.")
                locked_items = [
                    {"product": locked_products[item["product"].id], "quantity": item["quantity"]}
                    for item in items
                ]
                subtotal, delivery_fee, total = _cart_totals(locked_items)
                order = Order.objects.create(
                    **form.cleaned_data,
                    customer=request.user if customer_profile else None,
                    store=area["store"],
                    subtotal=subtotal,
                    delivery_fee=delivery_fee,
                    total=total,
                )
                for item in locked_items:
                    product = item["product"]
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        product_name=product.name,
                        unit_price=product.price,
                        quantity=item["quantity"],
                    )
                    product.stock -= item["quantity"]
                    product.save(update_fields=["stock"])
        except ValueError as error:
            messages.error(request, str(error))
            return redirect("website:cart")
        _send_order_confirmation(request, order)
        request.session["cart"] = {}
        request.session["last_order_reference"] = order.reference
        return redirect("website:order_success", reference=order.reference)
    return render(
        request,
        "website/checkout.html",
        {
            "items": items, "subtotal": subtotal, "delivery_fee": delivery_fee, "total": total,
            "form": form, "delivery_area": area,
        },
    )


def order_success(request, reference):
    order = get_object_or_404(Order.objects.prefetch_related("items"), reference=reference)
    owns_order = request.user.is_authenticated and order.customer_id == request.user.id
    is_recent_guest_order = request.session.get("last_order_reference") == order.reference
    if not owns_order and not is_recent_guest_order:
        return redirect("website:track_guest_order")
    return render(request, "website/order_success.html", {"order": order})
