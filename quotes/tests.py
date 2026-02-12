from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .models import FreightRateConfig, Quote
from .services.calculation import calculate_quote


class QuoteCalculationTests(SimpleTestCase):
    def test_air_chargeable_basis_weight(self):
        result = calculate_quote(
            transport_type="AIR",
            items_data=[
                {"weight_kg": "10", "length_cm": "30", "width_cm": "30", "height_cm": "30"},
                {"weight_kg": "20", "length_cm": "40", "width_cm": "30", "height_cm": "30"},
            ],
            air_rate_usd_per_kg=Decimal("4.5"),
            sea_rate_usd_per_m3=Decimal("120"),
            air_volumetric_factor=Decimal("6000"),
        )

        self.assertEqual(result["chargeable_basis"], "WEIGHT")
        self.assertEqual(result["chargeable_value"], Decimal("30.000"))
        self.assertEqual(result["total_usd"], Decimal("135.00"))

    def test_air_chargeable_basis_volume(self):
        result = calculate_quote(
            transport_type="AIR",
            items_data=[
                {"weight_kg": "5", "length_cm": "200", "width_cm": "100", "height_cm": "100"},
            ],
            air_rate_usd_per_kg=Decimal("4.5"),
            sea_rate_usd_per_m3=Decimal("120"),
            air_volumetric_factor=Decimal("6000"),
        )

        self.assertEqual(result["chargeable_basis"], "VOLUME")
        self.assertEqual(result["chargeable_value"], Decimal("333.333"))

    def test_sea_chargeable_by_volume(self):
        result = calculate_quote(
            transport_type="SEA",
            items_data=[
                {"weight_kg": "1", "length_cm": "100", "width_cm": "100", "height_cm": "100"},
            ],
            air_rate_usd_per_kg=Decimal("4.5"),
            sea_rate_usd_per_m3=Decimal("120"),
            air_volumetric_factor=Decimal("6000"),
        )

        self.assertEqual(result["chargeable_basis"], "VOLUME")
        self.assertEqual(result["volume_total_m3"], Decimal("1.000000"))
        self.assertEqual(result["total_usd"], Decimal("120.00"))


class QuotePermissionsAndAdminTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_user("admin1", password="adminpass123", is_staff=True)
        self.user_a = user_model.objects.create_user("user_a", password="userpass123")
        self.user_b = user_model.objects.create_user("user_b", password="userpass123")

    def _create_quote(self, user, total_usd: str):
        return Quote.objects.create(
            user=user,
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

    def test_admin_history_sees_all_quotes(self):
        quote_a = self._create_quote(self.user_a, "45.00")
        quote_b = self._create_quote(self.user_b, "90.00")
        self.client.login(username="admin1", password="adminpass123")
        response = self.client.get(reverse("quotes:quote_history"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(quote_a.id))
        self.assertContains(response, str(quote_b.id))
        self.assertContains(response, "user_a")
        self.assertContains(response, "user_b")

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

    def test_admin_can_update_rates_from_rates_page(self):
        self.client.login(username="admin1", password="adminpass123")
        response = self.client.post(
            reverse("quotes:admin_rates"),
            {
                "air_rate_usd_per_kg": "7.2500",
                "sea_rate_usd_per_m3": "180.0000",
                "air_volumetric_factor": "5500.000",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        config = FreightRateConfig.objects.order_by("-id").first()
        self.assertIsNotNone(config)
        self.assertEqual(config.air_rate_usd_per_kg, Decimal("7.2500"))

    def test_global_rates_are_used_for_new_quote(self):
        FreightRateConfig.objects.create(
            air_rate_usd_per_kg=Decimal("10.0000"),
            sea_rate_usd_per_m3=Decimal("200.0000"),
            air_volumetric_factor=Decimal("6000.000"),
            updated_by=self.admin,
        )
        self.client.login(username="user_a", password="userpass123")
        response = self.client.post(
            reverse("quotes:new_quote"),
            {
                "transport_type": "AIR",
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
        self.assertEqual(quote.rate_usd, Decimal("10.0000"))
        self.assertEqual(quote.total_usd, Decimal("100.00"))

    def test_logout_works_with_post(self):
        self.client.login(username="user_a", password="userpass123")
        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 302)
