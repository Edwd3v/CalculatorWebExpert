from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse

from quotes.models import AuditLog, Quote, RouteRate
from quotes.tests.base import QuoteTestDataMixin


class QuotePermissionsAndAdminTests(QuoteTestDataMixin):
    def test_regular_user_history_only_own_quotes(self):
        own_quote = self.create_quote(self.user_a, total_usd="45.00")
        self.create_quote(self.user_b, total_usd="90.00")
        self.client.login(username="user_a", password="userpass123")

        response = self.client.get(reverse("quotes:quote_history"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f">{own_quote.id}<", html=False)
        self.assertNotContains(response, "90.00")

    def test_admin_quote_history_redirects_to_admin_history(self):
        quote_a = self.create_quote(self.user_a, total_usd="45.00")
        quote_b = self.create_quote(self.user_b, total_usd="90.00")
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
        self.create_quote(self.user_a, total_usd="45.00")
        self.create_quote(self.user_b, total_usd="80.00", transport_type=Quote.TransportType.SEA)
        self.client.login(username="admin1", password="adminpass123")

        response = self.client.get(reverse("quotes:admin_history"), {"transport_type": "SEA"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Maritimo")
        self.assertContains(response, "user_b")
        self.assertNotContains(response, "user_a")

    def test_admin_history_csv_export_uses_filters(self):
        self.create_quote(self.user_a, total_usd="45.00")
        self.create_quote(self.user_b, total_usd="90.00")
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
                "rate-origin_country": self.country_name,
                "rate-destination_country": self.destination_name,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            RouteRate.objects.filter(
                origin_country=self.country_name,
                destination_country=self.destination_name,
                transport_type=Quote.TransportType.SEA,
                rate_usd=Decimal("0"),
            ).exists()
        )

    def test_new_rate_closes_previous_rate_automatically(self):
        self.client.login(username="admin1", password="adminpass123")
        first_rate = RouteRate.objects.create(
            origin_country=self.country_name,
            destination_country=self.destination_name,
            transport_type=Quote.TransportType.SEA,
            rate_usd=Decimal("5.0000"),
            is_active=True,
            updated_by=self.admin,
        )

        response = self.client.post(
            reverse("quotes:admin_rates"),
            {
                "create_rate": "1",
                "rate-transport_type": "SEA",
                "rate-origin_country": self.country_name,
                "rate-destination_country": self.destination_name,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        first_rate.refresh_from_db()
        self.assertFalse(first_rate.is_active)
        self.assertIsNotNone(first_rate.effective_to)

    def test_admin_rate_creation_logs_audit_event(self):
        self.client.login(username="admin1", password="adminpass123")
        self.client.post(
            reverse("quotes:admin_rates"),
            {
                "create_rate": "1",
                "rate-transport_type": "SEA",
                "rate-origin_country": self.country_name,
                "rate-destination_country": self.destination_name,
            },
            follow=True,
        )

        event = AuditLog.objects.filter(action="CREATE_RATE", model_name="RouteRate").first()
        self.assertIsNotNone(event)
        self.assertEqual(event.actor_id, self.admin.id)
        self.assertEqual(event.metadata.get("origin_country"), self.country_name)
        self.assertEqual(event.metadata.get("destination_country"), self.destination_name)

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

    def test_admin_tier_creation_returns_validation_error_without_crashing(self):
        self.client.login(username="admin1", password="adminpass123")

        response = self.client.post(
            reverse("quotes:admin_rates"),
            {
                "create_tier": "1",
                "transport": "AIR",
                "tier-route_rate": str(self.air_route_rate.id),
                "tier-min_weight_kg": "1.000",
                "tier-max_weight_kg": "10.000",
                "tier-rate_usd": "12.5000",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "El rango se superpone con otro tramo activo de la ruta.")

    def test_quote_uses_route_rate_and_generated_entry_points(self):
        self.client.login(username="user_a", password="userpass123")

        response = self.client.post(
            reverse("quotes:new_quote"),
            {
                "transport_type": "AIR",
                "origin_country": self.airport.country,
                "destination_country": self.destination_name,
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
        self.assertIsNotNone(quote.destination_location_id)
        self.assertEqual(quote.origin_country, self.airport.country)
        self.assertEqual(quote.destination_country, self.destination_name)
        self.assertEqual(quote.applied_route_rate_id, self.air_route_rate.id)

    def test_quote_fails_if_route_without_active_rate(self):
        self.client.login(username="user_a", password="userpass123")

        response = self.client.post(
            reverse("quotes:new_quote"),
            {
                "transport_type": "SEA",
                "origin_country": self.seaport.country,
                "destination_country": self.destination_name,
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
            destination_country=self.destination_name,
            applied_rate=None,
            applied_route_rate=self.air_route_rate,
            transport_type=Quote.TransportType.AIR,
            pieces_count=1,
            actual_weight_total_kg=Decimal("1234.560"),
            volumetric_weight_total_kg=Decimal("5.000"),
            volume_total_m3=Decimal("0.050000"),
            chargeable_basis=Quote.ChargeableBasis.WEIGHT,
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
