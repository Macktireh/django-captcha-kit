"""
Form field and widget rendering the configured CAPTCHA.

The tricky part is that the name of the submitted POST field is imposed by the
service (``cf-turnstile-response``, ``g-recaptcha-response``...) and has nothing
to do with the name the field is given in the Django form. It is resolved in
:meth:`CaptchaWidget.value_from_datadict`, which looks the value up under the
key the provider declares.
"""

from __future__ import annotations

from django import forms
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from .registry import get_captcha_provider


class CaptchaWidget(forms.Widget):
    """Widget delegating both rendering and field naming to the provider."""

    def __init__(self, alias: str | None = None, attrs=None) -> None:
        super().__init__(attrs)
        self.alias = alias

    @property
    def provider(self):
        return get_captcha_provider(self.alias)

    def render(self, name, value, attrs=None, renderer=None) -> str:
        return mark_safe(self.provider.render())

    def value_from_datadict(self, data, files, name):
        """Let the provider pick its own inputs out of the data, ignoring ``name``."""
        return self.provider.value_from_datadict(data)


class CaptchaField(forms.Field):
    """
    CAPTCHA field, usable in any form::

        class ContactForm(forms.Form):
            email = forms.EmailField()
            captcha = CaptchaField()

    Args:
        alias: Provider alias to use, or ``None`` for the configured default.
        attrs: HTML attributes forwarded to the widget.

    To pass the client IP on to the verification service, hand the request to
    the form through :class:`~captcha_kit.forms.CaptchaFormMixin`, or call
    :meth:`set_ip` manually.
    """

    widget = CaptchaWidget
    default_error_messages = {
        "required": _("Please complete the anti-bot verification."),
        "invalid": _("The anti-bot verification failed. Please try again."),
    }

    def __init__(self, alias: str | None = None, *, attrs=None, **kwargs) -> None:
        self.alias = alias
        self._attrs = dict(attrs or {})
        self._ip: str | None = None
        kwargs.setdefault("label", "")
        kwargs.setdefault("widget", CaptchaWidget(alias=alias))
        super().__init__(**kwargs)

    def widget_attrs(self, widget) -> dict:
        return dict(self._attrs)

    def set_ip(self, ip: str | None) -> None:
        """Attach the client IP sent to the provider as ``remoteip``."""
        self._ip = ip

    def validate(self, value) -> None:
        super().validate(value)
        if value in self.empty_values:
            return
        provider = get_captcha_provider(self.alias)
        if not provider.verify(value, ip=self._ip):
            raise forms.ValidationError(self.error_messages["invalid"], code="invalid")
