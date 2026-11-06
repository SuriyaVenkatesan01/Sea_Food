from .locations import selected_delivery_area


def cart_summary(request):
    cart = request.session.get("cart", {})
    postcode = request.session.get("delivery_postcode", "")
    area = selected_delivery_area(postcode, request.session.get("delivery_store_id"))
    return {
        "cart_count": sum(max(0, int(quantity)) for quantity in cart.values()),
        "delivery_postcode": area["postcode"] if area else "",
        "delivery_store": area["store"] if area else None,
        "delivery_prompt_dismissed": request.session.get("delivery_prompt_dismissed", False),
    }
