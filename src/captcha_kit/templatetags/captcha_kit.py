"""
``{% captcha %}`` template tag, for forms written by hand in a template.

When the form uses :class:`~captcha_kit.fields.CaptchaField`, rendering already
happens through ``{{ form.captcha }}`` and this tag is unnecessary::

    {% load captcha_kit %}
    <form method="post">
        {% csrf_token %}
        {% captcha %}
        <button>Send</button>
    </form>
"""

from django import template
from django.utils.safestring import mark_safe

from ..registry import get_captcha_provider

register = template.Library()


@register.simple_tag(name="captcha")
def captcha_tag(alias: str | None = None) -> str:
    """Render the widget of the provider registered under ``alias``."""
    return mark_safe(get_captcha_provider(alias).render())
