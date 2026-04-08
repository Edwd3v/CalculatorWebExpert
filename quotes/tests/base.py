from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from quotes.models import LocationRate, OriginLocation, Quote, RouteRate, RouteRateTier


class QuoteTestDataMixin(TestCase):
    def setUp(self):
        super().setUp()
        user_model = get_user_model()
        self.country_name = "Colombia"
        self.destination_name = "Estados Unidos"
        self.admin = user_model.objects.create_user("admin1", password="adminpass123", is_staff=True)
        self.user_a = user_model.objects.create_user("user_a", password="userpass123")
        self.user_b = user_model.objects.create_user("user_b", password="userpass123")
        self.airport = OriginLocation.objects.create(
            location_type=OriginLocation.LocationType.AIRPORT,
            code="BOG",
            name="El Dorado",
            country=self.country_name,
            is_active=True,
        )
        self.seaport = OriginLocation.objects.create(
            location_type=OriginLocation.LocationType.SEAPORT,
            code="CTG",
            name="Cartagena",
            country=self.country_name,
            is_active=True,
        )
        self.air_rate = LocationRate.objects.create(
            location=self.airport,
            usd_per_kg=Decimal("10.0000"),
            effective_from=date.today() - timedelta(days=1),
            is_active=True,
            updated_by=self.admin,
        )
        self.air_route_rate = RouteRate.objects.create(
            origin_country=self.country_name,
            destination_country=self.destination_name,
            transport_type=Quote.TransportType.AIR,
            rate_usd=Decimal("10.0000"),
            effective_from=date.today() - timedelta(days=1),
            is_active=True,
            updated_by=self.admin,
        )
        self.air_route_tier = RouteRateTier.objects.create(
            route_rate=self.air_route_rate,
            min_weight_kg=Decimal("0.000"),
            max_weight_kg=Decimal("99999.999"),
            rate_usd=Decimal("10.0000"),
            is_active=True,
        )

    def create_quote(self, user, *, total_usd: str, transport_type: str = Quote.TransportType.AIR):
        return Quote.objects.create(
            user=user,
            origin_location=self.airport if transport_type == Quote.TransportType.AIR else self.seaport,
            destination_location=self.seaport,
            origin_country=self.country_name,
            destination_country=self.destination_name,
            applied_rate=None,
            applied_route_rate=self.air_route_rate if transport_type == Quote.TransportType.AIR else None,
            transport_type=transport_type,
            pieces_count=1,
            actual_weight_total_kg=Decimal("10.000"),
            volumetric_weight_total_kg=Decimal("5.000"),
            volume_total_m3=Decimal("0.050000"),
            chargeable_basis=Quote.ChargeableBasis.WEIGHT,
            chargeable_value=Decimal("10.000"),
            rate_usd=Decimal("4.5000"),
            total_usd=Decimal(total_usd),
        )
