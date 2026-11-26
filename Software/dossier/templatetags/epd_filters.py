from datetime import date, datetime

from django import template
from django.utils.html import escape, mark_safe

from ..services import render_rich_text

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
def rich_html(value):
    """Render opgeslagen rich text veilig: HTML via nh3-sanering, gewone tekst
    met alinea's en regeleindes (zie services.render_rich_text)."""
    return render_rich_text(value)


# Oudere naam, gebruikt in bestaande templates; zelfde weergave als rich_html.
register.filter("safe_clean", rich_html)


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


@register.filter
def render_observations(value):
    """Render een lijst observaties als leesbare HTML-rijen (veiligs ge-escaped)."""
    if not isinstance(value, (list, tuple)):
        return mark_safe('<p class="muted">Nog geen observaties.</p>')
    rows = []
    for observation in value:
        if not isinstance(observation, dict):
            continue
        timestamp = format_field_value(observation.get("timestamp", ""), "datetime") or "Geen tijdstip"
        obs_value = escape(observation.get("value", ""))
        note = escape(observation.get("note", ""))
        rows.append(
            f'<div class="observation-row"><time>{escape(timestamp)}</time>'
            f"<strong>{obs_value}</strong><span>{note}</span></div>"
        )
    if not rows:
        return mark_safe('<p class="muted">Nog geen observaties.</p>')
    return mark_safe(f'<div class="observation-list">{"".join(rows)}</div>')
