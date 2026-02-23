from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .forms import QuoteForm
from .models import AuditLog, LocationRate, OriginLocation, Quote
from .services.calculation import calculate_quote
from .services.location_mapping import resolve_country_entry_point
from .templatetags.quotes_extras import es_number


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


class QuotePermissionsAndAdminTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.country_name = "Colombia"
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

    def _create_quote(self, user, total_usd: str):
        return Quote.objects.create(
            user=user,
            origin_location=self.airport,
            destination_location=self.airport,
            origin_country=self.airport.country,
            destination_country=self.airport.country,
            applied_rate=self.air_rate,
            transport_type="AIR",
            pieces_count=1,
            actual_weight_total_kg=Decimal("10.000"),
            volumetric_weight_total_kg=Decimal("5.000"),
            volume_total_m3=Decimal("0.050000"),
            chargeable_basis="WEIGHT",
            chargeable_value=Decimal("10.000"),
            rate_usd=Decimal("4.5000"),
            total_usd=Decimal(total_usd),
        )

    def test_regular_user_history_only_own_quotes(self):
        own_quote = self._create_quote(self.user_a, "45.00")
        self._create_quote(self.user_b, "90.00")
        self.client.login(username="user_a", password="userpass123")
        response = self.client.get(reverse("quotes:quote_history"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f">{own_quote.id}<", html=False)
        self.assertNotContains(response, "90.00")

    def test_admin_quote_history_redirects_to_admin_history(self):
        quote_a = self._create_quote(self.user_a, "45.00")
        quote_b = self._create_quote(self.user_b, "90.00")
        self.client.login(username="admin1", password="adminpass123")
        response = self.client.get(reverse("quotes:quote_history"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("quotes:admin_history"), response.url)

        redirected = self.client.get(response.url)
        self.assertEqual(redirected.status_code, 200)
        self.assertContains(redirected, str(quote_a.id))
        self.assertContains(redirected, str(quote_b.id))
        self.assertContains(redirected, "user_a")
        self.assertContains(redirected, "user_b")

    def test_admin_history_filters_by_transport_type(self):
        self._create_quote(self.user_a, "45.00")
        Quote.objects.create(
            user=self.user_b,
            origin_location=self.seaport,
            destination_location=self.seaport,
            origin_country=self.seaport.country,
            destination_country=self.seaport.country,
            transport_type="SEA",
            pieces_count=1,
            actual_weight_total_kg=Decimal("10.000"),
            volumetric_weight_total_kg=Decimal("5.000"),
            volume_total_m3=Decimal("0.050000"),
            chargeable_basis="WEIGHT",
            chargeable_value=Decimal("10.000"),
            rate_usd=Decimal("8.0000"),
            total_usd=Decimal("80.00"),
        )
        self.client.login(username="admin1", password="adminpass123")
        response = self.client.get(reverse("quotes:admin_history"), {"transport_type": "SEA"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Maritimo")
        self.assertContains(response, "user_b")
        self.assertNotContains(response, "user_a")

    def test_admin_history_csv_export_uses_filters(self):
        self._create_quote(self.user_a, "45.00")
        self._create_quote(self.user_b, "90.00")
        self.client.login(username="admin1", password="adminpass123")
        response = self.client.get(reverse("quotes:admin_history"), {"q": "user_a", "export": "csv"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("attachment;", response["Content-Disposition"])
        content = response.content.decode("utf-8")
        self.assertIn("user_a", content)
        self.assertNotIn("user_b", content)

    def test_non_admin_cannot_access_control_panel(self):
        self.client.login(username="user_a", password="userpass123")
        for route_name in ("quotes:admin_panel", "quotes:admin_rates", "quotes:admin_users", "quotes:admin_history"):
            response = self.client.get(reverse(route_name), follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "No tienes permisos")

    def test_admin_can_create_user_from_control_panel(self):
        self.client.login(username="admin1", password="adminpass123")
        response = self.client.post(
            reverse("quotes:admin_users"),
            {
                "username": "created_user",
                "email": "created@example.com",
                "first_name": "Created",
                "last_name": "User",
                "password1": "MyStrongPass123!",
                "password2": "MyStrongPass123!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(get_user_model().objects.filter(username="created_user").exists())

    def test_admin_can_create_location_rate_from_rates_page(self):
        self.client.login(username="admin1", password="adminpass123")
        response = self.client.post(
            reverse("quotes:admin_rates"),
            {
                "create_rate": "1",
                "rate-transport_type": "SEA",
                "rate-country": self.country_name,
                "rate-rate_usd": "7.2500",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(LocationRate.objects.filter(location=self.seaport, usd_per_kg=Decimal("7.2500")).exists())

    def test_new_rate_closes_previous_rate_automatically(self):
        self.client.login(username="admin1", password="adminpass123")
        first_rate = LocationRate.objects.create(
            location=self.seaport,
            usd_per_kg=Decimal("5.0000"),
            is_active=True,
            updated_by=self.admin,
        )
        response = self.client.post(
            reverse("quotes:admin_rates"),
            {
                "create_rate": "1",
                "rate-transport_type": "SEA",
                "rate-country": self.country_name,
                "rate-rate_usd": "6.0000",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        first_rate.refresh_from_db()
        self.assertFalse(first_rate.is_active)
        self.assertIsNotNone(first_rate.effective_to)

    def test_location_rate_unique_open_active_constraint(self):
        LocationRate.objects.create(
            location=self.seaport,
            usd_per_kg=Decimal("4.1000"),
            is_active=True,
            effective_to=None,
            updated_by=self.admin,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LocationRate.objects.create(
                    location=self.seaport,
                    usd_per_kg=Decimal("4.2000"),
                    is_active=True,
                    effective_to=None,
                    updated_by=self.admin,
                )

    def test_admin_rate_creation_logs_audit_event(self):
        self.client.login(username="admin1", password="adminpass123")
        self.client.post(
            reverse("quotes:admin_rates"),
            {
                "create_rate": "1",
                "rate-transport_type": "SEA",
                "rate-country": self.country_name,
                "rate-rate_usd": "9.9900",
            },
            follow=True,
        )
        event = AuditLog.objects.filter(action="CREATE_RATE", model_name="LocationRate").first()
        self.assertIsNotNone(event)
        self.assertEqual(event.actor_id, self.admin.id)
        self.assertEqual(event.metadata.get("country"), self.country_name)

    def test_admin_user_creation_logs_audit_event(self):
        self.client.login(username="admin1", password="adminpass123")
        self.client.post(
            reverse("quotes:admin_users"),
            {
                "username": "logged_user",
                "email": "logged@example.com",
                "first_name": "Logged",
                "last_name": "User",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
                "is_staff": "on",
            },
            follow=True,
        )
        event = AuditLog.objects.filter(action="CREATE_USER", model_name="User").first()
        self.assertIsNotNone(event)
        self.assertEqual(event.actor_id, self.admin.id)
        self.assertEqual(event.metadata.get("username"), "logged_user")

    def test_quote_uses_location_rate(self):
        self.client.login(username="user_a", password="userpass123")
        response = self.client.post(
            reverse("quotes:new_quote"),
            {
                "transport_type": "AIR",
                "origin_country": self.airport.country,
                "destination_country": self.airport.country,
                "pieces_count": "1",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "1",
                "items-MAX_NUM_FORMS": "200",
                "items-0-weight_kg": "10",
                "items-0-length_cm": "30",
                "items-0-width_cm": "30",
                "items-0-height_cm": "30",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        quote = Quote.objects.latest("id")
        self.assertEqual(quote.origin_location_id, self.airport.id)
        self.assertEqual(quote.destination_location_id, self.airport.id)
        self.assertEqual(quote.origin_country, self.airport.country)
        self.assertEqual(quote.destination_country, self.airport.country)
        self.assertEqual(quote.applied_rate_id, self.air_rate.id)

    def test_quote_fails_if_origin_without_active_rate(self):
        self.client.login(username="user_a", password="userpass123")
        response = self.client.post(
            reverse("quotes:new_quote"),
            {
                "transport_type": "SEA",
                "origin_country": self.seaport.country,
                "destination_country": self.seaport.country,
                "pieces_count": "1",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "1",
                "items-MAX_NUM_FORMS": "200",
                "items-0-weight_kg": "10",
                "items-0-length_cm": "30",
                "items-0-width_cm": "30",
                "items-0-height_cm": "30",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No existe una tarifa vigente")

    def test_quote_result_renders_localized_number_format(self):
        quote = Quote.objects.create(
            user=self.user_a,
            origin_location=self.airport,
            destination_location=self.airport,
            origin_country=self.airport.country,
            destination_country=self.airport.country,
            applied_rate=self.air_rate,
            transport_type="AIR",
            pieces_count=1,
            actual_weight_total_kg=Decimal("1234.560"),
            volumetric_weight_total_kg=Decimal("5.000"),
            volume_total_m3=Decimal("0.050000"),
            chargeable_basis="WEIGHT",
            chargeable_value=Decimal("1234.560"),
            rate_usd=Decimal("1000.5000"),
            total_usd=Decimal("1234567.8900"),
        )
        self.client.login(username="user_a", password="userpass123")
        response = self.client.get(reverse("quotes:quote_result", kwargs={"quote_id": quote.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1.234.567,89")
        self.assertContains(response, "1.000,5")
        self.assertContains(response, "1.234,56")

    def test_logout_works_with_post(self):
        self.client.login(username="user_a", password="userpass123")
        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 302)

    def test_quote_form_validation_does_not_create_entry_point_records(self):
        target_country = "Argentina"
        self.assertFalse(OriginLocation.objects.filter(country=target_country).exists())

        form = QuoteForm(
            data={
                "transport_type": "AIR",
                "origin_country": target_country,
                "destination_country": target_country,
                "pieces_count": "1",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertFalse(OriginLocation.objects.filter(country=target_country).exists())

    def test_country_code_legacy_is_normalized_for_entry_point_resolution(self):
        location = resolve_country_entry_point(country="CO", transport_type="AIR", create_missing=False)
        self.assertIsNotNone(location)
        self.assertEqual(location.id, self.airport.id)
