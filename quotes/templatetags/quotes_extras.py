from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import template

register = template.Library()


@register.filter
def es_number(value):
    """
    Format number using:
    - thousands separator: dot (.)
    - decimal separator: comma (,)
    - up to 2 decimals (no trailing zeros)
    """
    if value is None or value == "":
        return value

    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value

    rounded = number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "-" if rounded < 0 else ""
    abs_rounded = abs(rounded)
    integer_part, decimal_part = format(abs_rounded, "f").split(".")

    integer_formatted = f"{int(integer_part):,}".replace(",", ".")
    decimal_trimmed = decimal_part.rstrip("0")

    if decimal_trimmed:
        return f"{sign}{integer_formatted},{decimal_trimmed}"
    return f"{sign}{integer_formatted}"
