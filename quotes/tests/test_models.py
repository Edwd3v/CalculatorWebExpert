from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase

from quotes.models import AuditLog, LocationRate, Quote, RouteRate, RouteRateTier
from quotes.tests.base import QuoteTestDataMixin


class RouteRateModelTests(QuoteTestDataMixin):
    def test_route_rate_unique_open_active_constraint(self):
        RouteRate.objects.create(
            origin_country=self.country_name,
            destination_country=self.destination_name,
            transport_type=Quote.TransportType.SEA,
            rate_usd=Decimal("4.1000"),
            is_active=True,
            effective_to=None,
            updated_by=self.admin,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RouteRate.objects.create(
                    origin_country=self.country_name,
                    destination_country=self.destination_name,
                    transport_type=Quote.TransportType.SEA,
                    rate_usd=Decimal("4.2000"),
                    is_active=True,
                    effective_to=None,
                    updated_by=self.admin,
                )

    def test_location_rate_save_keeps_legacy_rate_fields_synchronized(self):
        rate = LocationRate.objects.create(
            location=self.seaport,
            usd_per_kg=Decimal("7.2500"),
            effective_from=self.air_rate.effective_from,
            is_active=True,
            updated_by=self.admin,
        )

        self.assertEqual(rate.usd_per_m3, Decimal("7.2500"))
        self.assertEqual(rate.rate_usd, Decimal("7.2500"))


class RouteRateTierModelTests(QuoteTestDataMixin):
    def test_tier_rejects_overlapping_ranges(self):
        overlapping_tier = RouteRateTier(
            route_rate=self.air_route_rate,
            min_weight_kg=Decimal("500.000"),
            max_weight_kg=Decimal("1500.000"),
            rate_usd=Decimal("9.5000"),
            is_active=True,
        )

        with self.assertRaisesMessage(ValidationError, "El rango se superpone con otro tramo activo de la ruta."):
            overlapping_tier.full_clean()

    def test_tier_without_overlap_is_valid(self):
        self.air_route_tier.is_active = False
        self.air_route_tier.save(update_fields=["is_active", "updated_at"])

        tier = RouteRateTier.objects.create(
            route_rate=self.air_route_rate,
            min_weight_kg=Decimal("1000.000"),
            max_weight_kg=None,
            rate_usd=Decimal("12.0000"),
            is_active=True,
        )

        self.assertEqual(tier.route_rate_id, self.air_route_rate.id)


class AuditLogModelTests(SimpleTestCase):
    def test_audit_log_string_representation_strips_empty_object_id(self):
        log = AuditLog(action="CREATE_USER", model_name="User", object_id="")
        self.assertEqual(str(log), "CREATE_USER User")
