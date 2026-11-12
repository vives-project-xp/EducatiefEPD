from django import template
from django.utils.html import mark_safe

from ..services import clean_html

register = template.Library()


@register.filter
def safe_clean(value):
    """Render opgeslagen rich text (TinyMCE-HTML) veilig via nh3-sanering."""
    return mark_safe(clean_html(value or ""))
