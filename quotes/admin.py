from django.contrib import admin

from .models import FreightRateConfig, Quote, QuoteItem


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
