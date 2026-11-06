import math
from decimal import Decimal, InvalidOperation

from .models import Store, StorePincode


def parse_coordinates(latitude, longitude):
    if not latitude and not longitude:
        return None, None
    try:
        latitude_value = Decimal(latitude)
        longitude_value = Decimal(longitude)
    except (InvalidOperation, TypeError):
        raise ValueError("Your location could not be read. Please try again or enter a PIN code.")
    if (
        not latitude_value.is_finite()
        or not longitude_value.is_finite()
        or not -90 <= latitude_value <= 90
        or not -180 <= longitude_value <= 180
    ):
        raise ValueError("Your location coordinates are invalid. Please try again.")
    return latitude_value, longitude_value


def nearest_store(latitude, longitude):
    candidates = Store.objects.filter(
        is_active=True,
        latitude__isnull=False,
        longitude__isnull=False,
    )
    eligible_stores = []
    for store in candidates:
        lat1, lat2 = math.radians(float(latitude)), math.radians(float(store.latitude))
        lat_delta = lat2 - lat1
        lon_delta = math.radians(float(store.longitude) - float(longitude))
        haversine = (
            math.sin(lat_delta / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(lon_delta / 2) ** 2
        )
        distance = 6371 * 2 * math.asin(min(1, math.sqrt(haversine)))
        if distance <= float(store.delivery_radius_km):
            eligible_stores.append((distance, store))
    if not eligible_stores:
        return None, None
    closest_distance, closest = min(eligible_stores, key=lambda match: match[0])
    return closest, Decimal(str(closest_distance)).quantize(Decimal("0.01"))


def resolve_delivery_area(postcode, latitude=None, longitude=None):
    if latitude is not None or longitude is not None:
        store, distance = nearest_store(latitude, longitude)
        if store is not None:
            return {
                "store": store,
                "postcode": postcode,
                "latitude": latitude,
                "longitude": longitude,
                "distance_km": distance,
                "location_based": True,
            }

    coverage = (
        StorePincode.objects.select_related("store")
        .filter(postcode=postcode, store__is_active=True)
        .first()
    )
    if coverage is None:
        return None
    return {
        "store": coverage.store,
        "postcode": coverage.postcode,
        "latitude": None,
        "longitude": None,
        "distance_km": None,
        "location_based": False,
    }


def selected_delivery_area(postcode, store_id):
    coverage = (
        StorePincode.objects.select_related("store")
        .filter(postcode=postcode, store_id=store_id, store__is_active=True)
        .first()
        if store_id
        else None
    )
    if coverage:
        return {
            "store": coverage.store,
            "postcode": postcode,
            "latitude": None,
            "longitude": None,
            "distance_km": None,
            "location_based": False,
        }
    return resolve_delivery_area(postcode)
