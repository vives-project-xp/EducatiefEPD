from django import template

from ..services import render_rich_text

register = template.Library()


@register.filter(name="rich_html")
def rich_html(value):
    """Toon opgeslagen tekst/HTML gesaneerd; vervangt autoescape off + linebreaks."""
    return render_rich_text(value)
