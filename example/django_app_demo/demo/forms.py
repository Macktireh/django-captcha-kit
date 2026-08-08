"""
The three ways to protect a form, side by side.

``ContactForm`` is the recommended one-liner. ``ProviderContactForm`` builds its
CAPTCHA field from an alias chosen at runtime, which the demo needs to render
every provider from a single view.
"""

from django import forms

from captcha_kit.fields import CaptchaField
from captcha_kit.forms import CaptchaFormMixin, get_client_ip


class BaseContactForm(forms.Form):
    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}))


class ContactForm(CaptchaFormMixin, BaseContactForm):
    """Uses the provider named by ``CAPTCHA_KIT['DEFAULT']``."""


class ProviderContactForm(BaseContactForm):
    """Uses the provider passed as ``alias``, whatever the default may be."""

    def __init__(self, *args, alias=None, request=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["captcha"] = CaptchaField(alias)
        if request is not None:
            self.fields["captcha"].set_ip(get_client_ip(request))
