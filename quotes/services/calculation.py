from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


THREE_DEC = Decimal("0.001")
FOUR_DEC = Decimal("0.0001")
SIX_DEC = Decimal("0.000001")
TWO_DEC = Decimal("0.01")
ONE_MILLION = Decimal("1000000")


@dataclass
class ItemCalculation:
    weight_kg: Decimal
    length_cm: Decimal
    width_cm: Decimal
    height_cm: Decimal
    volume_cm3: Decimal
    volumetric_weight_kg: Decimal


def quantize(value: Decimal, unit: Decimal) -> Decimal:
    return value.quantize(unit, rounding=ROUND_HALF_UP)


def calculate_quote(*, transport_type: str, items_data: list[dict], rate_usd: Decimal, volumetric_factor: Decimal) -> dict:
    item_results: list[ItemCalculation] = []
    total_actual_weight = Decimal("0")
    total_volumetric_weight = Decimal("0")
    total_volume_cm3 = Decimal("0")

    for item in items_data:
        weight = Decimal(item["weight_kg"])
        length = Decimal(item["length_cm"])
        width = Decimal(item["width_cm"])
        height = Decimal(item["height_cm"])

        volume_cm3 = length * width * height
        volumetric_weight = volume_cm3 / volumetric_factor

        total_actual_weight += weight
        total_volumetric_weight += volumetric_weight
        total_volume_cm3 += volume_cm3

        item_results.append(
            ItemCalculation(
                weight_kg=quantize(weight, THREE_DEC),
                length_cm=quantize(length, Decimal("0.01")),
                width_cm=quantize(width, Decimal("0.01")),
                height_cm=quantize(height, Decimal("0.01")),
                volume_cm3=quantize(volume_cm3, THREE_DEC),
                volumetric_weight_kg=quantize(volumetric_weight, THREE_DEC),
            )
        )

    total_volume_m3 = total_volume_cm3 / ONE_MILLION

    _ = transport_type  # Se conserva para trazabilidad de llamadas.
    # Regla de negocio: se cobra por la dimension mayor entre KG y M3 con tarifa unica.
    chargeable_basis = "WEIGHT" if total_actual_weight >= total_volume_m3 else "VOLUME"
    chargeable_value = total_actual_weight if chargeable_basis == "WEIGHT" else total_volume_m3
    total_usd = chargeable_value * rate_usd

    return {
        "items": item_results,
        "pieces_count": len(item_results),
        "actual_weight_total_kg": quantize(total_actual_weight, THREE_DEC),
        "volumetric_weight_total_kg": quantize(total_volumetric_weight, THREE_DEC),
        "volume_total_m3": quantize(total_volume_m3, SIX_DEC),
        "chargeable_basis": chargeable_basis,
        "chargeable_value": quantize(chargeable_value, THREE_DEC),
        "rate_usd": quantize(rate_usd, FOUR_DEC),
        "total_usd": quantize(total_usd, TWO_DEC),
    }
