from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.forms import BaseFormSet, formset_factory

from .models import LocationRate, OriginLocation, Quote


class QuoteForm(forms.Form):
    transport_type = forms.ChoiceField(choices=Quote.TransportType.choices, label="Tipo de transporte")
    origin_location = forms.ModelChoiceField(
        queryset=OriginLocation.objects.none(),
        label="Origen",
        empty_label="Selecciona origen",
    )
    pieces_count = forms.IntegerField(
        label="Cantidad de piezas",
        min_value=1,
        max_value=200,
        help_text="Se ajusta automaticamente el formulario de piezas.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["origin_location"].queryset = OriginLocation.objects.filter(is_active=True).order_by("location_type", "name")

    def clean(self):
        cleaned_data = super().clean()
        transport_type = cleaned_data.get("transport_type")
        origin_location = cleaned_data.get("origin_location")
        if not transport_type or not origin_location:
            return cleaned_data

        expected_type = OriginLocation.LocationType.AIRPORT if transport_type == Quote.TransportType.AIR else OriginLocation.LocationType.SEAPORT
        if origin_location.location_type != expected_type:
            self.add_error("origin_location", "El origen seleccionado no corresponde al tipo de transporte.")
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
    location = forms.ModelChoiceField(queryset=OriginLocation.objects.none(), label="Origen")
    rate_usd = forms.DecimalField(label="Tarifa unica (USD)", min_value=Decimal("0.0001"), max_digits=12, decimal_places=4)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["location"].queryset = OriginLocation.objects.filter(is_active=True).order_by("location_type", "name")
