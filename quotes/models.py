from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class OriginLocationQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def for_country_and_type(self, *, country: str, location_type: str):
        return self.active().filter(country=country, location_type=location_type)


class OriginLocation(models.Model):
    class LocationType(models.TextChoices):
        AIRPORT = "AIRPORT", "Aeropuerto"
        SEAPORT = "SEAPORT", "Puerto"

    name = models.CharField(max_length=120)
    code = models.CharField(max_length=12, unique=True)
    country = models.CharField(max_length=80)
    location_type = models.CharField(max_length=16, choices=LocationType.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = OriginLocationQuerySet.as_manager()

    class Meta:
        ordering = ["location_type", "code"]
        indexes = [
            models.Index(fields=["country", "location_type", "is_active"], name="quotes_origin_lookup_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class LocationRate(models.Model):
    location = models.ForeignKey(OriginLocation, on_delete=models.CASCADE, related_name="rates")
    usd_per_kg = models.DecimalField(max_digits=12, decimal_places=4)
    usd_per_m3 = models.DecimalField(max_digits=12, decimal_places=4)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_location_rates",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class QuerySet(models.QuerySet):
        def effective_on(self, target_date: date):
            return (
                self.filter(is_active=True, effective_from__lte=target_date)
                .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=target_date))
                .order_by("-effective_from", "-id")
            )

    objects = QuerySet.as_manager()

    class Meta:
        ordering = ["-effective_from", "-id"]
        indexes = [
            models.Index(fields=["location", "is_active", "effective_from"], name="quotes_loc_rate_lookup_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["location"],
                condition=Q(is_active=True, effective_to__isnull=True),
                name="uniq_open_active_rate_per_location",
            )
        ]

    def __str__(self) -> str:
        return f"{self.location.code} {self.effective_from}"

    @property
    def rate_usd(self):
        return self.usd_per_kg

    def save(self, *args, **kwargs):
        # Tarifa unica: mantenemos ambas columnas sincronizadas por compatibilidad.
        if self.usd_per_kg is not None:
            self.usd_per_m3 = self.usd_per_kg
        if not self.effective_from:
            self.effective_from = date.today()
        super().save(*args, **kwargs)


class RouteRate(models.Model):
    class TransportType(models.TextChoices):
        AIR = "AIR", "Aereo"
        SEA = "SEA", "Maritimo"

    origin_country = models.CharField(max_length=80)
    destination_country = models.CharField(max_length=80)
    transport_type = models.CharField(max_length=10, choices=TransportType.choices)
    rate_usd = models.DecimalField(max_digits=12, decimal_places=4)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_route_rates",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class QuerySet(models.QuerySet):
        def effective_on(self, target_date: date):
            return (
                self.filter(is_active=True, effective_from__lte=target_date)
                .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=target_date))
                .order_by("origin_country", "destination_country", "transport_type", "-effective_from", "-id")
            )

        def for_route(self, *, origin_country: str, destination_country: str, transport_type: str):
            return self.filter(
                origin_country=origin_country,
                destination_country=destination_country,
                transport_type=transport_type,
            )

    objects = QuerySet.as_manager()

    class Meta:
        ordering = ["origin_country", "destination_country", "transport_type", "-effective_from", "-id"]
        indexes = [
            models.Index(
                fields=["origin_country", "destination_country", "transport_type", "is_active"],
                name="quotes_route_lookup_idx",
            ),
            models.Index(fields=["transport_type", "effective_from"], name="quotes_route_transport_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["origin_country", "destination_country", "transport_type"],
                condition=Q(is_active=True, effective_to__isnull=True),
                name="uniq_open_active_route_rate",
            )
        ]

    def __str__(self) -> str:
        return f"{self.origin_country}->{self.destination_country} {self.transport_type} {self.effective_from}"

    def save(self, *args, **kwargs):
        if not self.effective_from:
            self.effective_from = date.today()
        super().save(*args, **kwargs)


class RouteRateTier(models.Model):
    route_rate = models.ForeignKey(RouteRate, on_delete=models.CASCADE, related_name="tiers")
    min_weight_kg = models.DecimalField(max_digits=12, decimal_places=3)
    max_weight_kg = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    rate_usd = models.DecimalField(max_digits=12, decimal_places=4)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class QuerySet(models.QuerySet):
        def active(self):
            return self.filter(is_active=True)

        def for_route_rate(self, route_rate: "RouteRate"):
            return self.active().filter(route_rate=route_rate).order_by("min_weight_kg", "id")

    objects = QuerySet.as_manager()

    class Meta:
        ordering = ["route_rate_id", "min_weight_kg", "id"]
        indexes = [
            models.Index(fields=["route_rate", "is_active", "min_weight_kg"], name="quotes_tier_lookup_idx"),
        ]

    def __str__(self) -> str:
        top = self.max_weight_kg if self.max_weight_kg is not None else "INF"
        return f"Tier {self.route_rate_id} [{self.min_weight_kg}, {top}]"

    def clean(self):
        if self.min_weight_kg is None:
            raise ValidationError({"min_weight_kg": "El peso minimo es obligatorio."})
        if self.min_weight_kg < Decimal("0"):
            raise ValidationError({"min_weight_kg": "El peso minimo no puede ser negativo."})
        if self.max_weight_kg is not None and self.max_weight_kg < self.min_weight_kg:
            raise ValidationError({"max_weight_kg": "El peso maximo debe ser mayor o igual al minimo."})

        if not self.route_rate_id:
            return

        others = RouteRateTier.objects.filter(route_rate_id=self.route_rate_id, is_active=True)
        if self.pk:
            others = others.exclude(pk=self.pk)

        new_min = self.min_weight_kg
        new_max = self.max_weight_kg

        for tier in others.only("min_weight_kg", "max_weight_kg").iterator():
            old_min = tier.min_weight_kg
            old_max = tier.max_weight_kg
            overlap = (new_max is None or old_min <= new_max) and (old_max is None or new_min <= old_max)
            if overlap:
                raise ValidationError("El rango se superpone con otro tramo activo de la ruta.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Quote(models.Model):
    class TransportType(models.TextChoices):
        AIR = "AIR", "Aereo"
        SEA = "SEA", "Maritimo"

    class ChargeableBasis(models.TextChoices):
        WEIGHT = "WEIGHT", "Peso"
        VOLUME = "VOLUME", "Volumen"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quotes")
    origin_location = models.ForeignKey(
        OriginLocation,
        on_delete=models.PROTECT,
        related_name="quotes",
        null=True,
        blank=True,
    )
    destination_location = models.ForeignKey(
        OriginLocation,
        on_delete=models.PROTECT,
        related_name="destination_quotes",
        null=True,
        blank=True,
    )
    origin_country = models.CharField(max_length=80, blank=True, default="")
    destination_country = models.CharField(max_length=80, blank=True, default="")
    applied_rate = models.ForeignKey(
        LocationRate,
        on_delete=models.SET_NULL,
        related_name="quotes",
        null=True,
        blank=True,
    )
    applied_route_rate = models.ForeignKey(
        RouteRate,
        on_delete=models.SET_NULL,
        related_name="quotes",
        null=True,
        blank=True,
    )
    applied_route_rate_tier = models.ForeignKey(
        RouteRateTier,
        on_delete=models.SET_NULL,
        related_name="quotes",
        null=True,
        blank=True,
    )
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

    class QuerySet(models.QuerySet):
        def with_result_related(self):
            return self.select_related(
                "user",
                "origin_location",
                "destination_location",
                "applied_rate",
                "applied_route_rate",
                "applied_route_rate_tier",
            ).prefetch_related("items")

        def with_history_related(self):
            return self.select_related("user", "origin_location", "destination_location")

        def for_user_access(self, user):
            queryset = self.with_result_related()
            if user.is_staff:
                return queryset
            return queryset.filter(user=user)

    objects = QuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"], name="quotes_user_created_idx"),
            models.Index(fields=["transport_type", "created_at"], name="quotes_transport_created_idx"),
            models.Index(fields=["created_at"], name="quotes_created_idx"),
        ]

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


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=80)
    model_name = models.CharField(max_length=80)
    object_id = models.CharField(max_length=64, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["action", "created_at"], name="quotes_audit_action_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.model_name} {self.object_id}".strip()
