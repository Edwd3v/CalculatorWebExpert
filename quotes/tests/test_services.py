from decimal import Decimal

from django.test import SimpleTestCase

from quotes.forms import QuoteForm
from quotes.services.calculation import calculate_quote
from quotes.services.location_mapping import resolve_country_entry_point
from quotes.templatetags.quotes_extras import es_number
from quotes.tests.base import QuoteTestDataMixin


class QuoteCalculationTests(SimpleTestCase):
    def test_chargeable_basis_weight_when_weight_total_is_higher(self):
        result = calculate_quote(
            transport_type="AIR",
            items_data=[{"weight_kg": "20", "length_cm": "100", "width_cm": "100", "height_cm": "100"}],
            rate_usd=Decimal("5.0"),
            volumetric_factor=Decimal("6000"),
        )

        self.assertEqual(result["chargeable_basis"], "WEIGHT")
        self.assertEqual(result["chargeable_value"], Decimal("20.000"))
        self.assertEqual(result["total_usd"], Decimal("100.00"))

    def test_chargeable_basis_volume_when_volume_total_is_higher(self):
        result = calculate_quote(
            transport_type="SEA",
            items_data=[{"weight_kg": "1", "length_cm": "200", "width_cm": "100", "height_cm": "100"}],
            rate_usd=Decimal("250.0"),
            volumetric_factor=Decimal("6000"),
        )

        self.assertEqual(result["chargeable_basis"], "VOLUME")
        self.assertEqual(result["chargeable_value"], Decimal("2.000"))
        self.assertEqual(result["total_usd"], Decimal("500.00"))


class NumberFormattingTests(SimpleTestCase):
    def test_es_number_formats_thousands_and_decimals(self):
        self.assertEqual(es_number(1234567.891), "1.234.567,89")
        self.assertEqual(es_number("1200"), "1.200")
        self.assertEqual(es_number(12.5), "12,5")
        self.assertEqual(es_number(0), "0")


class LocationMappingTests(QuoteTestDataMixin):
    def test_quote_form_validation_does_not_create_entry_point_records(self):
        target_country = "Argentina"
        self.assertFalse(resolve_country_entry_point(country=target_country, transport_type="AIR", create_missing=False))

        form = QuoteForm(
            data={
                "transport_type": "AIR",
                "origin_country": target_country,
                "destination_country": target_country,
                "pieces_count": "1",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertFalse(resolve_country_entry_point(country=target_country, transport_type="AIR", create_missing=False))

    def test_country_code_legacy_is_normalized_for_entry_point_resolution(self):
        location = resolve_country_entry_point(country="CO", transport_type="AIR", create_missing=False)
        self.assertIsNotNone(location)
        self.assertEqual(location.id, self.airport.id)
