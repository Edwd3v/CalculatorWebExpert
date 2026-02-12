from django.contrib import admin

from .models import FreightRateConfig, LocationRate, OriginLocation, Quote, QuoteItem


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
        "chargeable_basis",
        "chargeable_value",
        "total_usd",
        "created_at",
    )
    list_filter = ("transport_type", "chargeable_basis", "created_at")
    search_fields = ("user__username",)
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
