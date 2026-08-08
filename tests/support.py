"""Shared fixtures and helpers for the test suite."""

import json
from unittest import mock

from django import forms

from captcha_kit.forms import CaptchaFormMixin
from captcha_kit.providers.turnstile import TurnstileProvider

TURNSTILE_SETTINGS = {
    "DEFAULT": "turnstile",
    "PROVIDERS": {
        "turnstile": {"SITE_KEY": "sk", "SECRET_KEY": "secret"},
    },
}


class ContactForm(CaptchaFormMixin, forms.Form):
    email = forms.EmailField()


class FakeResponse:
    """Minimal stand-in for the object returned by ``urlopen``."""

    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self) -> bytes:
        return self.payload


def siteverify(body=None, error=None):
    """Patch the verification call with a canned response or an exception."""
    if error is not None:
        return mock.patch("captcha_kit.providers.base.urllib.request.urlopen", side_effect=error)
    payload = body if isinstance(body, bytes) else json.dumps(body).encode()
    return mock.patch(
        "captcha_kit.providers.base.urllib.request.urlopen",
        return_value=FakeResponse(payload),
    )


def patch_verify(result: bool):
    """Patch the whole verification step, for tests that only care about the outcome."""
    return mock.patch("captcha_kit.providers.base.SiteVerifyProvider.verify", return_value=result)


def turnstile(**options) -> TurnstileProvider:
    """Build a Turnstile provider directly, bypassing the settings."""
    return TurnstileProvider(site_key="sk", secret_key="secret", **options)
