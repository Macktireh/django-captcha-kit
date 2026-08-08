from django import forms
from django.test import override_settings

from captcha_kit.fields import CaptchaField
from captcha_kit.forms import CaptchaFormMixin
from tests.support import TURNSTILE_SETTINGS, ContactForm, patch_verify


@override_settings(CAPTCHA_KIT=TURNSTILE_SETTINGS)
def test_widget_reads_provider_field_from_post():
    with patch_verify(True) as verify:
        form = ContactForm({"email": "email@example.com", "cf-turnstile-response": "tok"})
        assert form.is_valid(), form.errors
    verify.assert_called_once()
    assert verify.call_args.args[0] == "tok"


def test_field_accepts_widget_attrs():
    field = CaptchaField(attrs={"data-theme": "dark"})
    assert field.widget.attrs["data-theme"] == "dark"


def test_field_accepts_an_explicit_widget():
    field = CaptchaField(widget=forms.HiddenInput())
    assert isinstance(field.widget, forms.HiddenInput)


def test_field_instances_do_not_share_the_client_ip():
    class OtherForm(CaptchaFormMixin, forms.Form):
        pass

    first = ContactForm()
    second = OtherForm()
    first.fields["captcha"].set_ip("10.0.0.1")
    assert second.fields["captcha"]._ip is None
