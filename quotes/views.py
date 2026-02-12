from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AdminUserCreationForm, FreightRateConfigForm, QuoteForm, QuoteItemFormSet
from .models import FreightRateConfig, Quote, QuoteItem
from .services.calculation import calculate_quote


def get_rate_config() -> FreightRateConfig:
    config = FreightRateConfig.objects.order_by("id").first()
    if config:
        return config
    return FreightRateConfig.objects.create(
        air_rate_usd_per_kg=Decimal(str(settings.AIR_RATE_USD_PER_KG)),
        sea_rate_usd_per_m3=Decimal(str(settings.SEA_RATE_USD_PER_M3)),
        air_volumetric_factor=Decimal(str(settings.AIR_VOLUMETRIC_FACTOR)),
    )


@login_required
def new_quote(request):
    if request.method == "POST":
        form = QuoteForm(request.POST)
        formset = QuoteItemFormSet(request.POST, prefix="items")

        if form.is_valid() and formset.is_valid():
            items_data = [item_form.cleaned_data for item_form in formset.forms if item_form.cleaned_data]
            expected_pieces = form.cleaned_data["pieces_count"]
            if expected_pieces != len(items_data):
                form.add_error(
                    "pieces_count",
                    f"La cantidad indicada ({expected_pieces}) no coincide con piezas cargadas ({len(items_data)}).",
                )
                return render(request, "quotes/new_quote.html", {"form": form, "formset": formset})

            rate_config = get_rate_config()
            result = calculate_quote(
                transport_type=form.cleaned_data["transport_type"],
                items_data=items_data,
                air_rate_usd_per_kg=rate_config.air_rate_usd_per_kg,
                sea_rate_usd_per_m3=rate_config.sea_rate_usd_per_m3,
                air_volumetric_factor=rate_config.air_volumetric_factor,
            )

            with transaction.atomic():
                quote = Quote.objects.create(
                    user=request.user,
                    transport_type=form.cleaned_data["transport_type"],
                    pieces_count=expected_pieces,
                    actual_weight_total_kg=result["actual_weight_total_kg"],
                    volumetric_weight_total_kg=result["volumetric_weight_total_kg"],
                    volume_total_m3=result["volume_total_m3"],
                    chargeable_basis=result["chargeable_basis"],
                    chargeable_value=result["chargeable_value"],
                    rate_usd=result["rate_usd"],
                    total_usd=result["total_usd"],
                )

                for item in result["items"]:
                    QuoteItem.objects.create(
                        quote=quote,
                        weight_kg=item.weight_kg,
                        length_cm=item.length_cm,
                        width_cm=item.width_cm,
                        height_cm=item.height_cm,
                        volume_cm3=item.volume_cm3,
                        volumetric_weight_kg=item.volumetric_weight_kg,
                    )

            messages.success(request, "Cotizacion creada correctamente.")
            return redirect("quotes:quote_result", quote_id=quote.id)
    else:
        form = QuoteForm(initial={"pieces_count": 1})
        formset = QuoteItemFormSet(prefix="items")

    return render(request, "quotes/new_quote.html", {"form": form, "formset": formset})


@login_required
def quote_result(request, quote_id: int):
    quote_query = Quote.objects.prefetch_related("items")
    if request.user.is_staff:
        quote = get_object_or_404(quote_query, id=quote_id)
    else:
        quote = get_object_or_404(quote_query, id=quote_id, user=request.user)
    basis_message = (
        "La carga se cotiza por PESO" if quote.chargeable_basis == Quote.ChargeableBasis.WEIGHT else "La carga se cotiza por VOLUMEN"
    )
    return render(request, "quotes/result.html", {"quote": quote, "basis_message": basis_message})


@login_required
def quote_history(request):
    if request.user.is_staff:
        quotes = Quote.objects.select_related("user").prefetch_related("items")
    else:
        quotes = Quote.objects.filter(user=request.user).prefetch_related("items")
    return render(request, "quotes/history.html", {"quotes": quotes, "is_admin": request.user.is_staff})


@login_required
def admin_panel(request):
    if not request.user.is_staff:
        messages.error(request, "No tienes permisos para acceder al panel de administracion.")
        return redirect("quotes:new_quote")

    rate_config = get_rate_config()

    if request.method == "POST":
        if "update_rates" in request.POST:
            rates_form = FreightRateConfigForm(request.POST, instance=rate_config)
            user_form = AdminUserCreationForm()
            if rates_form.is_valid():
                rate = rates_form.save(commit=False)
                rate.updated_by = request.user
                rate.save()
                messages.success(request, "Tarifas globales actualizadas.")
                return redirect("quotes:admin_panel")
        elif "create_user" in request.POST:
            user_form = AdminUserCreationForm(request.POST)
            rates_form = FreightRateConfigForm(instance=rate_config)
            if user_form.is_valid():
                user_form.save()
                messages.success(request, "Usuario creado correctamente.")
                return redirect("quotes:admin_panel")
        else:
            user_form = AdminUserCreationForm()
            rates_form = FreightRateConfigForm(instance=rate_config)
    else:
        user_form = AdminUserCreationForm()
        rates_form = FreightRateConfigForm(instance=rate_config)

    recent_users = (
        get_user_model().objects.filter(is_active=True).order_by("-date_joined")[:10]
    )
    return render(
        request,
        "quotes/admin_panel.html",
        {"user_form": user_form, "rates_form": rates_form, "rate_config": rate_config, "recent_users": recent_users},
    )


def home_redirect(request):
    if request.user.is_authenticated:
        return redirect("quotes:new_quote")
    return redirect("login")
