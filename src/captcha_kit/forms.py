"""
Form mixin wiring the CAPTCHA field and the client IP in a single line::

    class ContactForm(CaptchaFormMixin, forms.Form):
        email = forms.EmailField()
        message = forms.CharField(widget=forms.Textarea)

    form = ContactForm(request.POST, request=request)
"""

from __future__ import annotations

from django import forms

from .fields import CaptchaField
from .registry import get_config


def get_client_ip(request) -> str | None:
    """
    Return the client IP, honouring ``X-Forwarded-For`` only when it is trustworthy.

    ``X-Forwarded-For`` is attacker-controlled: any client can send it, and each
    proxy appends to it rather than replacing it. Only the entries appended by
    the proxies you own can be trusted, so the header is ignored unless
    ``CAPTCHA_KIT['TRUSTED_PROXY_COUNT']`` states how many of them sit in front
    of the application. With ``n`` trusted proxies, the client address is the
    ``n``-th entry counting from the right, so any value a client prepends to
    the header is ignored.
    """
    proxy_count = get_config()["TRUSTED_PROXY_COUNT"]
    remote_addr = request.META.get("REMOTE_ADDR")
    if not proxy_count:
        return remote_addr

    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    parts = [part.strip() for part in forwarded.split(",") if part.strip()]
    if len(parts) < proxy_count:
        return remote_addr
    return parts[-proxy_count]


class CaptchaFormMixin(forms.Form):
    """Adds a ``captcha`` field and forwards the client IP when given a request."""

    captcha = CaptchaField()

    def __init__(self, *args, request=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if request is not None:
            self.fields["captcha"].set_ip(get_client_ip(request))
