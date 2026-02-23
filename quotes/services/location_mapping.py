from hashlib import sha1

from django.conf import settings

from quotes.constants.country_aliases import COUNTRY_CODE_TO_NAME, COUNTRY_ENGLISH_TO_NAME
from quotes.constants.countries import WORLD_COUNTRY_NAMES
from quotes.models import OriginLocation, Quote


WORLD_COUNTRY_SET = set(WORLD_COUNTRY_NAMES)
WORLD_COUNTRY_LOWER_LOOKUP = {country.lower(): country for country in WORLD_COUNTRY_NAMES}


def _location_type_for_transport(transport_type: str) -> str:
    if transport_type == Quote.TransportType.AIR:
        return OriginLocation.LocationType.AIRPORT
    return OriginLocation.LocationType.SEAPORT


def get_available_countries() -> list[tuple[str, str]]:
    return [(country, country) for country in WORLD_COUNTRY_NAMES]


def normalize_country_name(country: str | None) -> str:
    if not country:
        return ""

    raw = str(country).strip()
    if not raw:
        return ""

    if raw in WORLD_COUNTRY_SET:
        return raw

    raw_upper = raw.upper()
    if raw_upper in COUNTRY_CODE_TO_NAME:
        mapped = COUNTRY_CODE_TO_NAME[raw_upper]
        if mapped in WORLD_COUNTRY_SET:
            return mapped

    raw_lower = raw.lower()
    if raw_lower in WORLD_COUNTRY_LOWER_LOOKUP:
        return WORLD_COUNTRY_LOWER_LOOKUP[raw_lower]

    if raw_lower in COUNTRY_ENGLISH_TO_NAME:
        mapped = COUNTRY_ENGLISH_TO_NAME[raw_lower]
        if mapped in WORLD_COUNTRY_SET:
            return mapped

    return raw


def _generated_entry_point_code(*, country: str, transport_type: str) -> str:
    digest = sha1(f"{transport_type}:{country}".encode("utf-8")).hexdigest()[:10].upper()
    prefix = "AIR" if transport_type == Quote.TransportType.AIR else "SEA"
    return f"{prefix}-{digest}"


def _generated_entry_point_name(*, country: str, transport_type: str) -> str:
    if transport_type == Quote.TransportType.AIR:
        return f"Hub principal {country}"
    return f"Puerto principal {country}"


def _find_generated_entry_point(*, country: str, transport_type: str) -> OriginLocation | None:
    code = _generated_entry_point_code(country=country, transport_type=transport_type)
    return OriginLocation.objects.filter(code=code, is_active=True).first()


def _get_or_create_generated_entry_point(*, country: str, transport_type: str) -> OriginLocation:
    code = _generated_entry_point_code(country=country, transport_type=transport_type)
    location_type = _location_type_for_transport(transport_type)
    defaults = {
        "name": _generated_entry_point_name(country=country, transport_type=transport_type),
        "country": country,
        "location_type": location_type,
        "is_active": True,
    }
    location, _ = OriginLocation.objects.get_or_create(code=code, defaults=defaults)
    return location


def resolve_country_entry_point(
    *,
    country: str,
    transport_type: str,
    create_missing: bool = False,
) -> OriginLocation | None:
    canonical_country = normalize_country_name(country)
    if canonical_country not in WORLD_COUNTRY_SET:
        return None

    preferred_by_type = getattr(settings, "COUNTRY_ENTRY_POINT_CODES", {})
    preferred_code = preferred_by_type.get(transport_type, {}).get(canonical_country)
    if preferred_code:
        expected_type = _location_type_for_transport(transport_type)
        preferred_location = OriginLocation.objects.filter(
            code=preferred_code,
            is_active=True,
            country=canonical_country,
            location_type=expected_type,
        ).first()
        if preferred_location:
            return preferred_location

    expected_type = _location_type_for_transport(transport_type)
    existing_location = (
        OriginLocation.objects.filter(
            is_active=True,
            country=canonical_country,
            location_type=expected_type,
        )
        .order_by("name", "code")
        .first()
    )
    if existing_location:
        return existing_location

    generated = _find_generated_entry_point(country=canonical_country, transport_type=transport_type)
    if generated:
        return generated

    if not create_missing:
        return None

    return _get_or_create_generated_entry_point(country=canonical_country, transport_type=transport_type)
