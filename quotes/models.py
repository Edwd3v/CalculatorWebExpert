from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Quote(models.Model):
    class TransportType(models.TextChoices):
        AIR = "AIR", "Aereo"
        SEA = "SEA", "Maritimo"

    class ChargeableBasis(models.TextChoices):
        WEIGHT = "WEIGHT", "Peso"
        VOLUME = "VOLUME", "Volumen"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quotes")
    transport_type = models.CharField(max_length=10, choices=TransportType.choices)
    pieces_count = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(200)])
    actual_weight_total_kg = models.DecimalField(max_digits=12, decimal_places=3)
    volumetric_weight_total_kg = models.DecimalField(max_digits=12, decimal_places=3)
    volume_total_m3 = models.DecimalField(max_digits=12, decimal_places=6)
    chargeable_basis = models.CharField(max_length=10, choices=ChargeableBasis.choices)
    chargeable_value = models.DecimalField(max_digits=12, decimal_places=3)
    rate_usd = models.DecimalField(max_digits=12, decimal_places=4)
    total_usd = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Quote #{self.pk} - {self.user}"


class FreightRateConfig(models.Model):
    air_rate_usd_per_kg = models.DecimalField(max_digits=12, decimal_places=4)
    sea_rate_usd_per_m3 = models.DecimalField(max_digits=12, decimal_places=4)
    air_volumetric_factor = models.DecimalField(max_digits=12, decimal_places=3)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_rate_configs",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuracion de tarifas"
        verbose_name_plural = "Configuracion de tarifas"

    def __str__(self) -> str:
        return f"Tarifas globales #{self.pk}"


class QuoteItem(models.Model):
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="items")
    weight_kg = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(0.001), MaxValueValidator(100000)],
    )
    length_cm = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01), MaxValueValidator(100000)],
    )
    width_cm = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01), MaxValueValidator(100000)],
    )
    height_cm = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01), MaxValueValidator(100000)],
    )
    volume_cm3 = models.DecimalField(max_digits=18, decimal_places=3)
    volumetric_weight_kg = models.DecimalField(max_digits=12, decimal_places=3)

    def __str__(self) -> str:
        return f"Item #{self.pk} - Quote #{self.quote_id}"
