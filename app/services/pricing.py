import math
from decimal import Decimal

from app.services.money import to_paise


def valid_coordinates(lat, lng):
    try:
        return math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180
    except (TypeError, ValueError):
        return False


def haversine_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculates straight-line ("as the crow flies") distance in kilometers
    between two lat/lng points using the haversine formula.
    """
    if not valid_coordinates(lat1, lng1) or not valid_coordinates(lat2, lng2):
        raise ValueError("Coordinates must be finite and within geographic bounds")
    R = 6371  # Earth's radius in kilometers

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    )
    a = min(1.0, max(0.0, a))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def calculate_price(distance_km: float) -> float:
    """
    Simple distance-based pricing:
    - Base fee of 100
    - Plus 10 per km of distance
    - Capped at a minimum of 100 (even for a very close reviewer)
    """
    if not math.isfinite(distance_km) or distance_km < 0:
        raise ValueError("Distance must be finite and non-negative")
    price = Decimal("100") + Decimal(str(distance_km)) * Decimal("10")
    return to_paise(price) / 100
