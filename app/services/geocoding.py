import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "TruStay/1.0 (dev project)"


def geocode_address(address: str) -> dict | None:
    """
    Looks up an address and returns {"lat": float, "lng": float} if found,
    or None if the address could not be resolved.
    """
    response = requests.get(
        NOMINATIM_URL,
        params={"q": address, "format": "json", "limit": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=10,
    )
    response.raise_for_status()
    results = response.json()

    if not results:
        return None

    return {"lat": float(results[0]["lat"]), "lng": float(results[0]["lon"])}
