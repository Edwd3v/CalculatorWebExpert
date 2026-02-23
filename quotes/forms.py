from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.forms import BaseFormSet, formset_factory

from .models import LocationRate, OriginLocation, Quote
from .services.location_mapping import get_available_countries, resolve_country_entry_point


class QuoteForm(forms.Form):
    transport_type = forms.ChoiceField(choices=Quote.TransportType.choices, label="Tipo de transporte")
    origin_country = forms.ChoiceField(choices=(), label="Pais de origen")
    destination_country = forms.ChoiceField(choices=(), label="Pais de destino")
    pieces_count = forms.IntegerField(
        label="Cantidad de piezas",
        min_value=1,
        max_value=200,
        help_text="Se ajusta automaticamente el formulario de piezas.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        countries = get_available_countries()
        country_choices = [("", "Selecciona pais")] + countries
        self.fields["origin_country"].choices = country_choices
        self.fields["destination_country"].choices = country_choices

    def clean(self):
        cleaned_data = super().clean()
        transport_type = cleaned_data.get("transport_type")
        origin_country = cleaned_data.get("origin_country")
        destination_country = cleaned_data.get("destination_country")
        if not transport_type or not origin_country or not destination_country:
            return cleaned_data

        if not resolve_country_entry_point(country=origin_country, transport_type=transport_type, create_missing=False):
            self.add_error(
                "origin_country",
                "No existe un punto de salida configurado para el pais de origen y tipo de transporte seleccionado.",
            )
        if not resolve_country_entry_point(country=destination_country, transport_type=transport_type, create_missing=False):
            self.add_error(
                "destination_country",
                "No existe un punto de llegada configurado para el pais de destino y tipo de transporte seleccionado.",
            )
        return cleaned_data


class QuoteItemInputForm(forms.Form):
    weight_kg = forms.DecimalField(label="Peso (kg)", min_value=Decimal("0.001"), max_digits=12, decimal_places=3)
    length_cm = forms.DecimalField(label="Largo (cm)", min_value=Decimal("0.01"), max_digits=12, decimal_places=2)
    width_cm = forms.DecimalField(label="Ancho (cm)", min_value=Decimal("0.01"), max_digits=12, decimal_places=2)
    height_cm = forms.DecimalField(label="Alto (cm)", min_value=Decimal("0.01"), max_digits=12, decimal_places=2)


class RequiredItemFormSet(BaseFormSet):
    def clean(self) -> None:
        super().clean()
        if any(self.errors):
            return

        valid_forms = [form for form in self.forms if form.cleaned_data]
        count = len(valid_forms)
        if count < 1:
            raise forms.ValidationError("Debe registrar al menos 1 pieza.")
        if count > 200:
            raise forms.ValidationError("No puede registrar mas de 200 piezas.")


QuoteItemFormSet = formset_factory(
    QuoteItemInputForm,
    formset=RequiredItemFormSet,
    extra=1,
    min_num=1,
    max_num=200,
    validate_min=True,
    validate_max=True,
)


User = get_user_model()


class AdminUserCreationForm(UserCreationForm):
    is_staff = forms.BooleanField(required=False, label="Crear como administrador")

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name")

    def save(self, commit: bool = True):
        user = super().save(commit=False)
        user.is_staff = self.cleaned_data["is_staff"]
        if commit:
            user.save()
        return user


class OriginLocationForm(forms.ModelForm):
    class Meta:
        model = OriginLocation
        fields = ("location_type", "code", "name", "country", "is_active")
        labels = {
            "location_type": "Tipo",
            "code": "Codigo",
            "name": "Nombre",
            "country": "Pais",
            "is_active": "Activo",
        }


class LocationRateForm(forms.Form):
    transport_type = forms.ChoiceField(choices=Quote.TransportType.choices, label="Tipo de transporte")
    country = forms.ChoiceField(choices=(), label="Pais")
    rate_usd = forms.DecimalField(label="Tarifa unica (USD)", min_value=Decimal("0.0001"), max_digits=12, decimal_places=4)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["country"].choices = [("", "Selecciona pais")] + get_available_countries()
