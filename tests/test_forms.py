from django.test import override_settings

from tests.support import TURNSTILE_SETTINGS, ContactForm, patch_verify


def test_form_valid_with_none_provider():
    form = ContactForm({"email": "email@example.com", "captcha": "1"})
    assert form.is_valid(), form.errors


def test_form_requires_captcha_value():
    form = ContactForm({"email": "email@example.com"})
    assert not form.is_valid()
    assert "captcha" in form.errors


@override_settings(CAPTCHA_KIT=TURNSTILE_SETTINGS)
def test_invalid_captcha_rejected():
    with patch_verify(False):
        form = ContactForm({"email": "email@example.com", "cf-turnstile-response": "bad"})
        assert not form.is_valid()
        assert "captcha" in form.errors


@override_settings(CAPTCHA_KIT=TURNSTILE_SETTINGS)
def test_ip_forwarded_from_request(rf):
    request = rf.post("/", {"email": "email@example.com", "cf-turnstile-response": "tok"})
    with patch_verify(True) as verify:
        form = ContactForm(request.POST, request=request)
        assert form.is_valid(), form.errors
    assert verify.call_args.kwargs["ip"] == "127.0.0.1"
