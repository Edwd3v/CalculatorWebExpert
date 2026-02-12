from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AdminUserCreationForm, LocationRateForm, OriginLocationForm, QuoteForm, QuoteItemFormSet
from .models import LocationRate, OriginLocation, Quote, QuoteItem
from .services.calculation import calculate_quote


def get_effective_rate(*, location: OriginLocation, on_date: date | None = None) -> LocationRate | None:
    target_date = on_date or date.today()
    return (
        LocationRate.objects.filter(location=location, is_active=True, effective_from__lte=target_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=target_date))
        .order_by("-effective_from", "-id")
        .first()
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

            origin_location = form.cleaned_data["origin_location"]
            applied_rate = get_effective_rate(location=origin_location)
            if not applied_rate:
                form.add_error("origin_location", "No existe una tarifa vigente para el origen seleccionado.")
                return render(request, "quotes/new_quote.html", {"form": form, "formset": formset})

            result = calculate_quote(
                transport_type=form.cleaned_data["transport_type"],
                items_data=items_data,
                rate_usd=applied_rate.rate_usd,
                volumetric_factor=Decimal(str(settings.AIR_VOLUMETRIC_FACTOR)),
            )

            with transaction.atomic():
                quote = Quote.objects.create(
                    user=request.user,
                    origin_location=origin_location,
                    applied_rate=applied_rate,
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
    quote_query = Quote.objects.select_related("origin_location", "applied_rate").prefetch_related("items")
    if request.user.is_staff:
        quote = get_object_or_404(quote_query, id=quote_id)
    else:
        quote = get_object_or_404(quote_query, id=quote_id, user=request.user)
    basis_message = (
        "Se cobra por KG (total mayor que M3 en costo)"
        if quote.chargeable_basis == Quote.ChargeableBasis.WEIGHT
        else "Se cobra por M3 (total mayor que KG en costo)"
    )
    return render(request, "quotes/result.html", {"quote": quote, "basis_message": basis_message})


@login_required
def quote_history(request):
    if request.user.is_staff:
        quotes = Quote.objects.select_related("user", "origin_location").prefetch_related("items")
    else:
        quotes = Quote.objects.filter(user=request.user).select_related("origin_location").prefetch_related("items")
    return render(request, "quotes/history.html", {"quotes": quotes, "is_admin": request.user.is_staff})


@login_required
def admin_panel(request):
    if not request.user.is_staff:
        messages.error(request, "No tienes permisos para acceder al panel de administracion.")
        return redirect("quotes:new_quote")

    user_model = get_user_model()
    stats = {
        "total_users": user_model.objects.filter(is_active=True).count(),
        "admin_users": user_model.objects.filter(is_active=True, is_staff=True).count(),
        "total_quotes": Quote.objects.count(),
        "total_airports": OriginLocation.objects.filter(location_type=OriginLocation.LocationType.AIRPORT, is_active=True).count(),
        "total_seaports": OriginLocation.objects.filter(location_type=OriginLocation.LocationType.SEAPORT, is_active=True).count(),
    }
    return render(request, "quotes/admin_panel.html", {"stats": stats})


@login_required
def admin_rates(request):
    if not request.user.is_staff:
        messages.error(request, "No tienes permisos para acceder al panel de administracion.")
        return redirect("quotes:new_quote")

    if request.method == "POST":
        if "create_location" in request.POST:
            location_form = OriginLocationForm(request.POST, prefix="loc")
            rate_form = LocationRateForm(prefix="rate")
            if location_form.is_valid():
                location_form.save()
                messages.success(request, "Origen creado correctamente.")
                return redirect("quotes:admin_rates")
        elif "create_rate" in request.POST:
            rate_form = LocationRateForm(request.POST, prefix="rate")
            location_form = OriginLocationForm(prefix="loc")
            if rate_form.is_valid():
                location = rate_form.cleaned_data["location"]
                rate_value = rate_form.cleaned_data["rate_usd"]
                today = date.today()
                # Cierra vigencia previa activa del mismo origen cuando entra una nueva tarifa.
                LocationRate.objects.filter(
                    location=location,
                    is_active=True,
                    effective_to__isnull=True,
                ).update(effective_to=today, is_active=False)
                new_rate = LocationRate(
                    location=location,
                    usd_per_kg=rate_value,
                    usd_per_m3=rate_value,
                    effective_from=today,
                    is_active=True,
                )
                new_rate.updated_by = request.user
                new_rate.save()
                messages.success(request, "Tarifa creada correctamente.")
                return redirect("quotes:admin_rates")
        else:
            location_form = OriginLocationForm(prefix="loc")
            rate_form = LocationRateForm(prefix="rate")
    else:
        location_form = OriginLocationForm(prefix="loc")
        rate_form = LocationRateForm(prefix="rate")

    airports = OriginLocation.objects.filter(location_type=OriginLocation.LocationType.AIRPORT).order_by("code")
    seaports = OriginLocation.objects.filter(location_type=OriginLocation.LocationType.SEAPORT).order_by("code")
    today = date.today()
    airports_with_rates = [(location, get_effective_rate(location=location, on_date=today)) for location in airports]
    seaports_with_rates = [(location, get_effective_rate(location=location, on_date=today)) for location in seaports]

    return render(
        request,
        "quotes/admin_rates.html",
        {
            "location_form": location_form,
            "rate_form": rate_form,
            "airports_with_rates": airports_with_rates,
            "seaports_with_rates": seaports_with_rates,
        },
    )


@login_required
def admin_users(request):
    if not request.user.is_staff:
        messages.error(request, "No tienes permisos para acceder al panel de administracion.")
        return redirect("quotes:new_quote")

    if request.method == "POST":
        user_form = AdminUserCreationForm(request.POST)
        if user_form.is_valid():
            user_form.save()
            messages.success(request, "Usuario creado correctamente.")
            return redirect("quotes:admin_users")
    else:
        user_form = AdminUserCreationForm()

    recent_users = get_user_model().objects.filter(is_active=True).order_by("-date_joined")[:20]
    return render(request, "quotes/admin_users.html", {"user_form": user_form, "recent_users": recent_users})


@login_required
def admin_history(request):
    if not request.user.is_staff:
        messages.error(request, "No tienes permisos para acceder al panel de administracion.")
        return redirect("quotes:new_quote")

    recent_quotes = Quote.objects.select_related("user", "origin_location").prefetch_related("items").order_by("-created_at")[:30]
    return render(request, "quotes/admin_history.html", {"recent_quotes": recent_quotes})


def home_redirect(request):
    if request.user.is_authenticated:
        return redirect("quotes:new_quote")
    return redirect("login")
