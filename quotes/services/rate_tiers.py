from decimal import Decimal

from quotes.models import RouteRate, RouteRateTier


def resolve_route_rate_tier(*, route_rate: RouteRate, weight_kg: Decimal) -> RouteRateTier | None:
    tiers = RouteRateTier.objects.for_route_rate(route_rate)
    for tier in tiers:
        upper_ok = tier.max_weight_kg is None or weight_kg <= tier.max_weight_kg
        if tier.min_weight_kg <= weight_kg and upper_ok:
            return tier
    return None
