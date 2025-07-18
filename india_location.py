# india_location.py
"""
Location normalization helper for Siddharth Astrology.

- Uses OpenStreetMap Nominatim via geopy.
- Forces country=India context when possible.
- Returns clean string: "India → <state> → <district/city>" when data found.
- Gracefully falls back to user input.

NOTE: Nominatim has usage limits. In production, consider caching.
"""

from geopy.geocoders import Nominatim

_geolocator = None

def _get_geolocator():
    global _geolocator
    if _geolocator is None:
        # user_agent required by Nominatim policy
        _geolocator = Nominatim(user_agent="siddharth_astrology_app")
    return _geolocator

def normalize_location(user_text: str) -> str:
    """
    Attempt to geocode user input inside India.
    Returns a descriptive string suitable for including in AI prompts.
    """
    if not user_text:
        return "India"

    geo = _get_geolocator()
    try:
        # Append India to bias search
        loc = geo.geocode(f"{user_text}, India", addressdetails=True, language="en", country_codes="IN")
    except Exception:
        loc = None

    if not loc or not getattr(loc, "raw", None):
        return f"India → {user_text}"

    addr = loc.raw.get("address", {})
    # Common keys in Nominatim: state, state_district, county, city, town, village, suburb
    state = addr.get("state") or addr.get("region")
    district = (
        addr.get("state_district")
        or addr.get("county")
        or addr.get("city")
        or addr.get("town")
        or addr.get("village")
        or addr.get("suburb")
    )

    if state and district:
        return f"India → {state} → {district}"
    elif state:
        return f"India → {state}"
    else:
        return f"India → {user_text}"
