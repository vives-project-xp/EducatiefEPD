from datetime import date, datetime

from django import template
from django.utils.html import mark_safe

from ..services import clean_html

register = template.Library()

MONTHS_NL = [
    "januari", "februari", "maart", "april", "mei", "juni",
    "juli", "augustus", "september", "oktober", "november", "december",
]


def _parse_date(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    text = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


@register.filter
def safe_clean(value):
    """Render opgeslagen rich text (TinyMCE-HTML) veilig via nh3-sanering."""
    return mark_safe(clean_html(value or ""))


@register.filter
def format_field_value(value, field_type):
    """Zet een veldwaarde om naar een leesbare weergave per veldtype."""
    if value is None or value == "":
        return ""
    if field_type in ("date", "datetime"):
        parsed = _parse_date(value)
        if parsed:
            nice = f"{parsed.day} {MONTHS_NL[parsed.month - 1]} {parsed.year}"
            if field_type == "datetime" and (parsed.hour or parsed.minute):
                nice += f" {parsed:%H:%M}"
            return nice
        return str(value)
    if field_type == "number":
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        formatted = f"{number:,.2f}".replace(".", "@").replace(",", ".").replace("@", ",")
        if formatted.endswith(",00"):
            formatted = formatted[:-3]
        return formatted
    if isinstance(value, (list, tuple)):
        return "; ".join(str(entry) for entry in value)
    return str(value)
