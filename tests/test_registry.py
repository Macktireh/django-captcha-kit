import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from captcha_kit.registry import get_captcha_provider
from tests.support import TURNSTILE_SETTINGS


def test_none_provider_by_default():
    provider = get_captcha_provider()
    assert provider.field() == "captcha"
    assert provider.verify("anything") is True


def test_provider_instance_is_reused():
    assert get_captcha_provider() is get_captcha_provider()


def test_override_settings_invalidates_the_provider_cache():
    assert get_captcha_provider().field() == "captcha"
    with override_settings(CAPTCHA_KIT=TURNSTILE_SETTINGS):
        assert get_captcha_provider().field() == "cf-turnstile-response"
    assert get_captcha_provider().field() == "captcha"


@override_settings(CAPTCHA_KIT=TURNSTILE_SETTINGS)
def test_builtin_alias_needs_no_explicit_backend():
    provider = get_captcha_provider()
    assert provider.field() == "cf-turnstile-response"
    assert 'data-sitekey="sk"' in provider.render()


@override_settings(CAPTCHA_KIT={"DEFAULT": "ghost", "PROVIDERS": {}})
def test_unknown_alias_raises_improperly_configured():
    with pytest.raises(ImproperlyConfigured, match="unknown provider"):
        get_captcha_provider()


@override_settings(
    CAPTCHA_KIT={
        "DEFAULT": "custom",
        "PROVIDERS": {"custom": {"BACKEND": "captcha_kit.registry.DEFAULTS"}},
    }
)
def test_backend_that_is_not_a_class_raises_improperly_configured():
    with pytest.raises(ImproperlyConfigured, match="must be a subclass"):
        get_captcha_provider()
