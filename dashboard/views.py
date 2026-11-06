from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.core.paginator import Paginator
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import ProductForm, StoreForm, StorePincodeFormSet
from website.models import ContactInquiry, Order, Product, Store


def staff_login(request):
    next_url = request.GET.get("next", "")
    login_url = reverse("website:login")
    if next_url:
        login_url = f"{login_url}?{urlencode({'next': next_url})}"
    return redirect(login_url)


@staff_member_required(login_url="dashboard:login")
def overview(request):
    month_start = timezone.localdate().replace(day=1)
    delivered = Order.objects.exclude(status=Order.Status.CANCELLED)
    sales = delivered.aggregate(total=Sum("total"))["total"] or Decimal("0.00")
    month_sales = delivered.filter(created_at__date__gte=month_start).aggregate(total=Sum("total"))["total"] or Decimal("0.00")
    daily = []
    today = timezone.localdate()
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        amount = (
            delivered.filter(created_at__date=day)
            .aggregate(total=Sum("total"))["total"]
            or Decimal("0.00")
        )
        daily.append({"label": day.strftime("%a"), "amount": amount})
    max_amount = max((day["amount"] for day in daily), default=Decimal("0"))
    for day in daily:
        day["height"] = int(day["amount"] * 100 / max_amount) if max_amount else 0
    low_stock_products = Product.objects.filter(is_active=True, stock__lte=5).order_by("stock", "name")
    context = {
        "sales_total": sales,
        "month_sales": month_sales,
        "order_count": Order.objects.count(),
        "pending_count": Order.objects.filter(status__in=[Order.Status.NEW, Order.Status.CONFIRMED]).count(),
        "product_count": Product.objects.filter(is_active=True).count(),
        "low_stock": low_stock_products[:5],
        "low_stock_count": low_stock_products.count(),
        "recent_orders": Order.objects.select_related("store").prefetch_related("items")[:8],
        "daily_sales": daily,
        "max_day_sales": max_amount,
        "status_choices": Order.Status.choices,
    }
    return render(request, "dashboard/overview.html", context)


@staff_member_required(login_url="dashboard:login")
def products(request):
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    availability = request.GET.get("availability", "")
    product_list = Product.objects.all()
    if query:
        product_list = product_list.filter(Q(name__icontains=query) | Q(slug__icontains=query))
    if category in Product.Category.values:
        product_list = product_list.filter(category=category)
    if availability == "active":
        product_list = product_list.filter(is_active=True)
    elif availability == "inactive":
        product_list = product_list.filter(is_active=False)
    page = Paginator(product_list, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/products.html",
        {
            "page": page,
            "products": page.object_list,
            "query": query,
            "category": category,
            "availability": availability,
            "categories": Product.Category.choices,
        },
    )


@staff_member_required(login_url="dashboard:login")
def product_create(request):
    form = ProductForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        product = form.save()
        messages.success(request, f"{product.name} was added to your catalog.")
        return redirect("dashboard:products")
    return render(request, "dashboard/product_form.html", {"form": form, "is_new": True})


@staff_member_required(login_url="dashboard:login")
def product_edit(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    form = ProductForm(request.POST or None, instance=product)
    if request.method == "POST" and form.is_valid():
        product = form.save()
        messages.success(request, f"{product.name} was updated.")
        return redirect("dashboard:products")
    return render(
        request,
        "dashboard/product_form.html",
        {"form": form, "product": product, "is_new": False},
    )


@staff_member_required(login_url="dashboard:login")
def stores(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    store_list = Store.objects.prefetch_related("service_areas").all()
    if query:
        store_list = store_list.filter(
            Q(name__icontains=query)
            | Q(city__icontains=query)
            | Q(service_areas__postcode__icontains=query)
        ).distinct()
    if status == "active":
        store_list = store_list.filter(is_active=True)
    elif status == "inactive":
        store_list = store_list.filter(is_active=False)
    page = Paginator(store_list, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/stores.html",
        {
            "page": page,
            "stores": page.object_list,
            "query": query,
            "status": status,
        },
    )


@staff_member_required(login_url="dashboard:login")
def store_create(request):
    return _store_form(request)


@staff_member_required(login_url="dashboard:login")
def store_edit(request, store_id):
    return _store_form(request, store=get_object_or_404(Store, id=store_id))


def _store_form(request, store=None):
    is_new = store is None
    form = StoreForm(request.POST or None, instance=store)
    formset = StorePincodeFormSet(request.POST or None, instance=store)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            saved_store = form.save()
            formset.instance = saved_store
            formset.save()
        messages.success(
            request,
            f"{saved_store.name} was {'added' if is_new else 'updated'} with its delivery PIN codes.",
        )
        return redirect("dashboard:stores")
    return render(
        request,
        "dashboard/store_form.html",
        {
            "form": form,
            "formset": formset,
            "store": store,
            "is_new": is_new,
        },
    )


@staff_member_required(login_url="dashboard:login")
def orders(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    order_list = Order.objects.select_related("store").prefetch_related("items")
    if query:
        order_list = order_list.filter(
            Q(reference__icontains=query)
            | Q(full_name__icontains=query)
            | Q(phone__icontains=query)
            | Q(email__icontains=query)
            | Q(store__name__icontains=query)
        )
    if status in Order.Status.values:
        order_list = order_list.filter(status=status)
    page = Paginator(order_list, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/orders.html",
        {
            "page": page,
            "orders": page.object_list,
            "query": query,
            "selected_status": status,
            "status_choices": Order.Status.choices,
        },
    )


@staff_member_required(login_url="dashboard:login")
def contacts(request):
    query = request.GET.get("q", "").strip()
    contact_list = ContactInquiry.objects.all()
    if query:
        contact_list = contact_list.filter(
            Q(name__icontains=query)
            | Q(phone__icontains=query)
            | Q(email__icontains=query)
            | Q(subject__icontains=query)
            | Q(message__icontains=query)
        )
    page = Paginator(contact_list, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/contacts.html",
        {"page": page, "contacts": page.object_list, "query": query},
    )


@staff_member_required(login_url="dashboard:login")
def inquiries(request):
    query = request.GET.get("q", "").strip()
    inquiry_list = ContactInquiry.objects.all()
    if query:
        inquiry_list = inquiry_list.filter(
            Q(name__icontains=query)
            | Q(email__icontains=query)
            | Q(phone__icontains=query)
            | Q(subject__icontains=query)
            | Q(message__icontains=query)
        )
    page = Paginator(inquiry_list, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/inquiries.html",
        {"page": page, "inquiries": page.object_list, "query": query},
    )


@staff_member_required(login_url="dashboard:login")
@require_POST
def resolve_inquiry(request, inquiry_id):
    inquiry = get_object_or_404(ContactInquiry, id=inquiry_id)
    inquiry.is_resolved = not inquiry.is_resolved
    inquiry.save(update_fields=["is_resolved"])
    messages.success(
        request,
        f"Message from {inquiry.name} marked {'resolved' if inquiry.is_resolved else 'open'}.",
    )
    return redirect("dashboard:inquiries")


@staff_member_required(login_url="dashboard:login")
@require_POST
def update_order_status(request, order_id):
    status = request.POST.get("status", "")
    if status not in Order.Status.values:
        messages.error(request, "Choose a valid order status.")
    else:
        with transaction.atomic():
            order = get_object_or_404(Order.objects.select_for_update(), id=order_id)
            if order.status == Order.Status.CANCELLED and status != Order.Status.CANCELLED:
                messages.error(request, "Cancelled orders cannot be reopened.")
            else:
                if status == Order.Status.CANCELLED and order.status != Order.Status.CANCELLED:
                    for item in order.items.select_related("product"):
                        product = item.product
                        product.stock += item.quantity
                        product.save(update_fields=["stock"])
                order.status = status
                order.save(update_fields=["status"])
                messages.success(request, f"Order #{order.reference} updated.")
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("dashboard:overview")
