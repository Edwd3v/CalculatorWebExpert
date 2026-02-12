from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ExchangeRate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(unique=True)),
                ("usd_to_cop", models.DecimalField(decimal_places=4, max_digits=12)),
                ("source", models.CharField(default="API", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-date"]},
        ),
        migrations.CreateModel(
            name="Quote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "transport_type",
                    models.CharField(choices=[("AIR", "Aereo"), ("SEA", "Maritimo")], max_length=10),
                ),
                (
                    "pieces_count",
                    models.PositiveIntegerField(
                        validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(200)]
                    ),
                ),
                ("actual_weight_total_kg", models.DecimalField(decimal_places=3, max_digits=12)),
                ("volumetric_weight_total_kg", models.DecimalField(decimal_places=3, max_digits=12)),
                ("volume_total_m3", models.DecimalField(decimal_places=6, max_digits=12)),
                (
                    "chargeable_basis",
                    models.CharField(choices=[("WEIGHT", "Peso"), ("VOLUME", "Volumen")], max_length=10),
                ),
                ("chargeable_value", models.DecimalField(decimal_places=3, max_digits=12)),
                ("rate_usd", models.DecimalField(decimal_places=4, max_digits=12)),
                ("trm_usd_cop", models.DecimalField(decimal_places=4, max_digits=12)),
                ("total_usd", models.DecimalField(decimal_places=2, max_digits=12)),
                ("total_cop", models.DecimalField(decimal_places=2, max_digits=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="quotes", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="QuoteItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "weight_kg",
                    models.DecimalField(
                        decimal_places=3,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(0.001), django.core.validators.MaxValueValidator(100000)],
                    ),
                ),
                (
                    "length_cm",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(0.01), django.core.validators.MaxValueValidator(100000)],
                    ),
                ),
                (
                    "width_cm",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(0.01), django.core.validators.MaxValueValidator(100000)],
                    ),
                ),
                (
                    "height_cm",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(0.01), django.core.validators.MaxValueValidator(100000)],
                    ),
                ),
                ("volume_cm3", models.DecimalField(decimal_places=3, max_digits=18)),
                ("volumetric_weight_kg", models.DecimalField(decimal_places=3, max_digits=12)),
                (
                    "quote",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="quotes.quote"),
                ),
            ],
        ),
    ]
