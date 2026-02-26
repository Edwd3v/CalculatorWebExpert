from datetime import date, timedelta
from decimal import Decimal
import csv
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .constants.countries import WORLD_COUNTRY_NAMES
from .forms import AdminUserCreationForm, LocationRateForm, QuoteForm, QuoteItemFormSet, RouteRateTierForm
from .models import LocationRate, OriginLocation, Quote, QuoteItem, RouteRate, RouteRateTier
from .services.audit import log_admin_action
from .services.calculation import calculate_quote
from .services.location_mapping import normalize_country_name, resolve_country_entry_point
from .services.rate_tiers import resolve_route_rate_tier


def get_effective_rate(*, location: OriginLocation, on_date: date | None = None) -> LocationRate | None:
    target_date = on_date or date.today()
    return (
        LocationRate.objects.filter(location=location, is_active=True, effective_from__lte=target_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=target_date))
        .order_by("-effective_from", "-id")
        .first()
    )


def get_effective_route_rate(
    *,
    origin_country: str,
    destination_country: str,
    transport_type: str,
    on_date: date | None = None,
) -> RouteRate | None:
    target_date = on_date or date.today()
    return (
        RouteRate.objects.filter(
            origin_country=origin_country,
            destination_country=destination_country,
            transport_type=transport_type,
            is_active=True,
            effective_from__lte=target_date,
        )
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

            transport_type = form.cleaned_data["transport_type"]
            origin_country = normalize_country_name(form.cleaned_data["origin_country"])
            destination_country = normalize_country_name(form.cleaned_data["destination_country"])

            origin_location = resolve_country_entry_point(
                country=origin_country,
                transport_type=transport_type,
                create_missing=True,
            )
            destination_location = resolve_country_entry_point(
                country=destination_country,
                transport_type=transport_type,
                create_missing=True,
            )
            if not origin_location:
                form.add_error("origin_country", "No hay un punto de salida configurado para el pais seleccionado.")
                return render(request, "quotes/new_quote.html", {"form": form, "formset": formset})
            if not destination_location:
                form.add_error("destination_country", "No hay un punto de llegada configurado para el pais seleccionado.")
                return render(request, "quotes/new_quote.html", {"form": form, "formset": formset})

            applied_route_rate = get_effective_route_rate(
                origin_country=origin_country,
                destination_country=destination_country,
                transport_type=transport_type,
            )
            if not applied_route_rate:
                form.add_error(
                    "destination_country",
                    "No existe una tarifa vigente para la ruta origen-destino seleccionada.",
                )
                return render(request, "quotes/new_quote.html", {"form": form, "formset": formset})

            pre_result = calculate_quote(
                transport_type=transport_type,
                items_data=items_data,
                rate_usd=Decimal("0"),
                volumetric_factor=Decimal(str(settings.AIR_VOLUMETRIC_FACTOR)),
            )
            applied_tier = resolve_route_rate_tier(
                route_rate=applied_route_rate,
                weight_kg=pre_result["actual_weight_total_kg"],
            )
            if not applied_tier:
                form.add_error(
                    "destination_country",
                    "No existe un tramo tarifario vigente para el peso total de la mercancia en esta ruta.",
                )
                return render(request, "quotes/new_quote.html", {"form": form, "formset": formset})

            result = calculate_quote(
                transport_type=transport_type,
                items_data=items_data,
                rate_usd=applied_tier.rate_usd,
                volumetric_factor=Decimal(str(settings.AIR_VOLUMETRIC_FACTOR)),
            )

            with transaction.atomic():
                quote = Quote.objects.create(
                    user=request.user,
                    origin_location=origin_location,
                    destination_location=destination_location,
                    origin_country=origin_country,
                    destination_country=destination_country,
                    applied_rate=None,
                    applied_route_rate=applied_route_rate,
                    applied_route_rate_tier=applied_tier,
                    transport_type=transport_type,
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
    quote_query = Quote.objects.select_related("origin_location", "destination_location", "applied_rate", "applied_route_rate").prefetch_related("items")
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
        return redirect("quotes:admin_history")

    quotes = (
        Quote.objects.filter(user=request.user).select_related("origin_location", "destination_location").prefetch_related("items")
    )
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
        "total_countries": len(WORLD_COUNTRY_NAMES),
        "countries_with_air_rate": (
            RouteRate.objects.filter(is_active=True, transport_type=Quote.TransportType.AIR)
            .values("origin_country")
            .distinct()
            .count()
        ),
        "countries_with_sea_rate": (
            RouteRate.objects.filter(is_active=True, transport_type=Quote.TransportType.SEA)
            .values("origin_country")
            .distinct()
            .count()
        ),
    }
    return render(request, "quotes/admin_panel.html", {"stats": stats})


@login_required
def admin_rates(request):
    if not request.user.is_staff:
        messages.error(request, "No tienes permisos para acceder al panel de administracion.")
        return redirect("quotes:new_quote")

    allowed_transports = {choice[0] for choice in Quote.TransportType.choices}
    active_transport = (
        request.POST.get("transport")
        or request.POST.get("rate-transport_type")
        or request.GET.get("transport")
        or Quote.TransportType.AIR
    ).upper()
    if active_transport not in allowed_transports:
        active_transport = Quote.TransportType.AIR

    def redirect_to_active_transport():
        return redirect(f"{reverse('quotes:admin_rates')}?{urlencode({'transport': active_transport})}")

    if request.method == "POST":
        if "create_rate" in request.POST:
            rate_form = LocationRateForm(request.POST, prefix="rate")
            tier_form = RouteRateTierForm(prefix="tier", transport_type=active_transport)
            if rate_form.is_valid():
                origin_country = normalize_country_name(rate_form.cleaned_data["origin_country"])
                destination_country = normalize_country_name(rate_form.cleaned_data["destination_country"])
                if origin_country == destination_country:
                    messages.error(request, "Origen y destino no pueden ser iguales para configurar una ruta.")
                    return redirect_to_active_transport()
                today = date.today()
                try:
                    with transaction.atomic():
                        # Lock de tarifas abiertas de la misma ruta para evitar colisiones concurrentes.
                        open_rates = RouteRate.objects.select_for_update().filter(
                            origin_country=origin_country,
                            destination_country=destination_country,
                            transport_type=active_transport,
                            is_active=True,
                            effective_to__isnull=True,
                        )
                        open_rates.update(effective_to=today, is_active=False)

                        new_rate = RouteRate(
                            origin_country=origin_country,
                            destination_country=destination_country,
                            transport_type=active_transport,
                            rate_usd=Decimal("0"),
                            effective_from=today,
                            is_active=True,
                        )
                        new_rate.updated_by = request.user
                        new_rate.save()

                        log_admin_action(
                            actor=request.user,
                            action="CREATE_RATE",
                            model_name="RouteRate",
                            object_id=new_rate.id,
                            metadata={
                                "origin_country": origin_country,
                                "destination_country": destination_country,
                                "transport_type": active_transport,
                                "rate_usd": Decimal("0"),
                            },
                        )
                except IntegrityError:
                    messages.error(
                        request,
                        "No fue posible guardar la tarifa por una actualizacion concurrente. Intenta nuevamente.",
                    )
                    return redirect_to_active_transport()
                messages.success(request, "Tarifa creada correctamente.")
                return redirect_to_active_transport()
        elif "create_tier" in request.POST:
            tier_form = RouteRateTierForm(request.POST, prefix="tier", transport_type=active_transport)
            rate_form = LocationRateForm(prefix="rate")
            if tier_form.is_valid():
                route_rate = tier_form.cleaned_data["route_rate"]
                min_weight = tier_form.cleaned_data["min_weight_kg"]
                max_weight = tier_form.cleaned_data["max_weight_kg"]
                rate_value = tier_form.cleaned_data["rate_usd"]
                try:
                    with transaction.atomic():
                        new_tier = RouteRateTier.objects.create(
                            route_rate=route_rate,
                            min_weight_kg=min_weight,
                            max_weight_kg=max_weight,
                            rate_usd=rate_value,
                            is_active=True,
                        )
                        log_admin_action(
                            actor=request.user,
                            action="CREATE_ROUTE_RATE_TIER",
                            model_name="RouteRateTier",
                            object_id=new_tier.id,
                            metadata={
                                "route_rate_id": route_rate.id,
                                "min_weight_kg": min_weight,
                                "max_weight_kg": max_weight,
                                "rate_usd": rate_value,
                            },
                        )
                except Exception as exc:
                    tier_form.add_error(None, str(exc))
                else:
                    messages.success(request, "Tramo tarifario creado correctamente.")
                    return redirect_to_active_transport()
        elif "deactivate_tier" in request.POST:
            tier_form = RouteRateTierForm(prefix="tier", transport_type=active_transport)
            rate_form = LocationRateForm(prefix="rate")
            tier_id = request.POST.get("tier_id", "").strip()
            tier = RouteRateTier.objects.filter(
                id=tier_id,
                is_active=True,
                route_rate__transport_type=active_transport,
            ).first()
            if tier:
                tier.is_active = False
                tier.save(update_fields=["is_active", "updated_at"])
                log_admin_action(
                    actor=request.user,
                    action="DEACTIVATE_ROUTE_RATE_TIER",
                    model_name="RouteRateTier",
                    object_id=tier.id,
                    metadata={"route_rate_id": tier.route_rate_id},
                )
                messages.success(request, "Tramo desactivado.")
                return redirect_to_active_transport()
        else:
            rate_form = LocationRateForm(prefix="rate")
            tier_form = RouteRateTierForm(prefix="tier", transport_type=active_transport)
    else:
        rate_form = LocationRateForm(prefix="rate")
        tier_form = RouteRateTierForm(prefix="tier", transport_type=active_transport)

    today = date.today()
    effective_route_rows = (
        RouteRate.objects.filter(
            is_active=True,
            effective_from__lte=today,
            transport_type=active_transport,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
        .order_by("origin_country", "destination_country", "transport_type", "-effective_from", "-id")
    )
    route_rows = []
    for route_rate in effective_route_rows:
        route_rows.append(
            {
                "origin_country": route_rate.origin_country,
                "destination_country": route_rate.destination_country,
                "transport_type": route_rate.transport_type,
                "rate": route_rate,
            }
        )
    active_tiers = RouteRateTier.objects.select_related("route_rate").filter(
        is_active=True,
        route_rate__transport_type=active_transport,
    ).order_by(
        "route_rate__origin_country",
        "route_rate__destination_country",
        "route_rate__transport_type",
        "min_weight_kg",
    )

    return render(
        request,
        "quotes/admin_rates.html",
        {
            "rate_form": rate_form,
            "tier_form": tier_form,
            "route_rows": route_rows,
            "active_tiers": active_tiers,
            "active_transport": active_transport,
            "transport_tabs": Quote.TransportType.choices,
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
            new_user = user_form.save()
            log_admin_action(
                actor=request.user,
                action="CREATE_USER",
                model_name="User",
                object_id=new_user.id,
                metadata={
                    "username": new_user.username,
                    "is_staff": new_user.is_staff,
                },
            )
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

    query = request.GET.get("q", "").strip()
    transport_filter = request.GET.get("transport_type", "").strip()
    date_from_raw = request.GET.get("date_from", "").strip()
    date_to_raw = request.GET.get("date_to", "").strip()

    def parse_date(value: str) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    date_from = parse_date(date_from_raw)
    date_to = parse_date(date_to_raw)

    filtered_quotes = Quote.objects.select_related("user", "origin_location", "destination_location").prefetch_related("items")
    if query:
        filtered_quotes = filtered_quotes.filter(
            Q(user__username__icontains=query)
            | Q(origin_country__icontains=query)
            | Q(destination_country__icontains=query)
        )
    if transport_filter in {Quote.TransportType.AIR, Quote.TransportType.SEA}:
        filtered_quotes = filtered_quotes.filter(transport_type=transport_filter)
    if date_from:
        filtered_quotes = filtered_quotes.filter(created_at__date__gte=date_from)
    if date_to:
        filtered_quotes = filtered_quotes.filter(created_at__date__lte=date_to)

    filtered_quotes = filtered_quotes.order_by("-created_at")

    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="historial_operativo.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "ID",
                "Usuario",
                "Transporte",
                "Origen",
                "Destino",
                "Base",
                "Total USD",
                "Fecha",
            ]
        )
        for quote in filtered_quotes:
            writer.writerow(
                [
                    quote.id,
                    quote.user.username,
                    quote.get_transport_type_display(),
                    quote.origin_country,
                    quote.destination_country,
                    quote.get_chargeable_basis_display(),
                    str(quote.total_usd),
                    quote.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                ]
            )
        return response

    paginator = Paginator(filtered_quotes, 30)
    page_obj = paginator.get_page(request.GET.get("page"))

    week_start = timezone.now() - timedelta(days=7)
    weekly_quotes = Quote.objects.filter(created_at__gte=week_start)
    weekly_total = weekly_quotes.count()
    weekly_avg = weekly_quotes.aggregate(avg_total=Avg("total_usd"))["avg_total"] or Decimal("0")

    top_route_row = (
        weekly_quotes.values("origin_country", "destination_country")
        .annotate(total=Count("id"))
        .order_by("-total", "origin_country", "destination_country")
        .first()
    )
    if top_route_row and top_route_row.get("origin_country") and top_route_row.get("destination_country"):
        top_route = f'{top_route_row["origin_country"]} a {top_route_row["destination_country"]}'
    else:
        top_route = "-"

    transport_counts = weekly_quotes.values("transport_type").annotate(total=Count("id"))
    air_count = next((row["total"] for row in transport_counts if row["transport_type"] == Quote.TransportType.AIR), 0)
    sea_count = next((row["total"] for row in transport_counts if row["transport_type"] == Quote.TransportType.SEA), 0)
    if weekly_total:
        air_pct = (air_count * 100) / weekly_total
        sea_pct = (sea_count * 100) / weekly_total
    else:
        air_pct = 0
        sea_pct = 0

    metrics = {
        "weekly_total": weekly_total,
        "weekly_avg": weekly_avg,
        "top_route": top_route,
        "air_pct": round(air_pct, 1),
        "sea_pct": round(sea_pct, 1),
    }
    filter_params = {}
    if query:
        filter_params["q"] = query
    if transport_filter in {Quote.TransportType.AIR, Quote.TransportType.SEA}:
        filter_params["transport_type"] = transport_filter
    if date_from_raw:
        filter_params["date_from"] = date_from_raw
    if date_to_raw:
        filter_params["date_to"] = date_to_raw
    query_string = urlencode(filter_params)

    return render(
        request,
        "quotes/admin_history.html",
        {
            "recent_quotes": page_obj.object_list,
            "page_obj": page_obj,
            "metrics": metrics,
            "filters": {
                "q": query,
                "transport_type": transport_filter,
                "date_from": date_from_raw,
                "date_to": date_to_raw,
            },
            "query_string": query_string,
        },
    )


def home_redirect(request):
    if request.user.is_authenticated:
        return redirect("quotes:new_quote")
    return redirect("login")
