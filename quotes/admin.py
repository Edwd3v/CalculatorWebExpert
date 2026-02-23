from django.contrib import admin

from .models import AuditLog, FreightRateConfig, LocationRate, OriginLocation, Quote, QuoteItem, RouteRate, RouteRateTier


class QuoteItemInline(admin.TabularInline):
    model = QuoteItem
    extra = 0
    readonly_fields = (
        "weight_kg",
        "length_cm",
        "width_cm",
        "height_cm",
        "volume_cm3",
        "volumetric_weight_kg",
    )


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "transport_type",
        "origin_country",
        "destination_country",
        "chargeable_basis",
        "chargeable_value",
        "total_usd",
        "created_at",
    )
    list_filter = ("transport_type", "chargeable_basis", "created_at")
    search_fields = ("user__username", "origin_country", "destination_country")
    inlines = [QuoteItemInline]


@admin.register(FreightRateConfig)
class FreightRateConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "air_rate_usd_per_kg", "sea_rate_usd_per_m3", "air_volumetric_factor", "updated_by", "updated_at")


@admin.register(OriginLocation)
class OriginLocationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "location_type", "country", "is_active")
    list_filter = ("location_type", "is_active", "country")
    search_fields = ("code", "name", "country")


@admin.register(LocationRate)
class LocationRateAdmin(admin.ModelAdmin):
    list_display = ("location", "usd_per_kg", "effective_from", "effective_to", "is_active", "updated_by")
    list_filter = ("location__location_type", "is_active", "effective_from")
    search_fields = ("location__code", "location__name")


@admin.register(RouteRate)
class RouteRateAdmin(admin.ModelAdmin):
    list_display = ("origin_country", "destination_country", "transport_type", "rate_usd", "effective_from", "effective_to", "is_active")
    list_filter = ("transport_type", "is_active", "effective_from")
    search_fields = ("origin_country", "destination_country")


@admin.register(RouteRateTier)
class RouteRateTierAdmin(admin.ModelAdmin):
    list_display = ("route_rate", "min_weight_kg", "max_weight_kg", "rate_usd", "is_active", "updated_at")
    list_filter = ("is_active", "route_rate__transport_type")
    search_fields = ("route_rate__origin_country", "route_rate__destination_country")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "model_name", "object_id")
    list_filter = ("action", "model_name", "created_at")
    search_fields = ("actor__username", "action", "model_name", "object_id")
